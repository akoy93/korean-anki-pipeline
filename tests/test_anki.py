from __future__ import annotations

import base64
import shutil
import unittest
from pathlib import Path
from unittest.mock import patch

from korean_anki.anki_client import ANKI_MODEL_NAME, AnkiConnectClient
from korean_anki.anki_media_sync import sync_batch_media, sync_lesson_media
from korean_anki.anki_push_service import plan_push, push_batch
from korean_anki.note_generation import generate_note
from korean_anki.schema import LessonDocument, MediaAsset

from support import make_batch, make_item, make_metadata


class FakeAnkiConnectClient:
    instances: list["FakeAnkiConnectClient"] = []
    existing_note_ids: list[int] = []
    notes_info: list[dict[str, object]] = []
    add_notes_result: list[int | None] = []
    media_files: dict[str, bytes] = {}

    def __init__(self, url: str = "http://127.0.0.1:8765") -> None:
        self.url = url
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.synced = False
        self.stored_media: list[str] = []
        type(self).instances.append(self)

    @classmethod
    def reset(cls) -> None:
        cls.instances = []
        cls.existing_note_ids = []
        cls.notes_info = []
        cls.add_notes_result = []
        cls.media_files = {}

    def invoke(self, action: str, **params: object) -> object:
        self.calls.append((action, params))
        if action == "findNotes":
            return self.existing_note_ids
        if action == "notesInfo":
            return self.notes_info
        if action == "modelNames":
            return [ANKI_MODEL_NAME]
        if action == "createDeck":
            return None
        if action == "createModel":
            return None
        if action == "addNotes":
            return self.add_notes_result
        if action == "retrieveMediaFile":
            filename = params["filename"]
            if isinstance(filename, str) and filename in self.media_files:
                return base64.b64encode(self.media_files[filename]).decode("ascii")
            return False
        if action == "sync":
            self.synced = True
            return None
        return None

    def ensure_deck(self, deck_name: str) -> None:
        self.invoke("createDeck", deck=deck_name)

    def ensure_model(self) -> None:
        self.invoke("modelNames")

    def store_media_file(self, path: str) -> str:
        name = Path(path).name
        self.stored_media.append(name)
        return name

    def retrieve_media_file(self, filename: str) -> bytes | None:
        encoded = self.invoke("retrieveMediaFile", filename=filename)
        if not isinstance(encoded, str):
            return None
        return base64.b64decode(encoded)

    def sync(self) -> None:
        self.invoke("sync")


class AnkiTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeAnkiConnectClient.reset()

    def test_plan_push_detects_duplicates_and_counts_approved_cards(self) -> None:
        item = make_item(
            item_id="item-1",
            korean="일",
            english="one",
            item_type="number",
            audio=MediaAsset(path="preview/public/media/audio/item-1.mp3"),
            tags=["numbers"],
        )
        note = generate_note(item)
        note.cards[-1] = note.cards[-1].model_copy(update={"approved": False})
        batch = make_batch([note])

        FakeAnkiConnectClient.existing_note_ids = [123]
        FakeAnkiConnectClient.notes_info = [
            {
                "noteId": 123,
                "fields": {
                    "Korean": {"value": "일"},
                    "English": {"value": "one"},
                },
            }
        ]

        with (
            patch("korean_anki.anki_push_service.AnkiConnectClient", FakeAnkiConnectClient),
            patch("korean_anki.anki_queries.AnkiConnectClient", FakeAnkiConnectClient),
        ):
            result = plan_push(batch)

        self.assertEqual(result.deck_name, "Korean::Lessons::Basics")
        self.assertEqual(result.approved_notes, 1)
        self.assertEqual(result.approved_cards, 3)
        self.assertFalse(result.can_push)
        self.assertEqual(len(result.duplicate_notes), 1)
        self.assertEqual(result.duplicate_notes[0].existing_note_id, 123)

    def test_push_batch_uploads_media_adds_notes_and_syncs(self) -> None:
        audio_path = Path("tests/tmp-audio.mp3")
        image_path = Path("tests/tmp-image.png")
        audio_path.write_bytes(b"audio")
        image_path.write_bytes(b"image")
        self.addCleanup(audio_path.unlink, missing_ok=True)
        self.addCleanup(image_path.unlink, missing_ok=True)

        item = make_item(
            item_id="item-1",
            korean="안녕하세요",
            english="hello",
            audio=MediaAsset(path=str(audio_path)),
            image=MediaAsset(path=str(image_path)),
            tags=["greetings"],
        )
        batch = make_batch([generate_note(item)], metadata=make_metadata(target_deck="Korean::Lessons::Greetings"))
        FakeAnkiConnectClient.add_notes_result = [456]

        with (
            patch("korean_anki.anki_push_service.AnkiConnectClient", FakeAnkiConnectClient),
            patch("korean_anki.anki_queries.AnkiConnectClient", FakeAnkiConnectClient),
        ):
            result = push_batch(batch)

        self.assertEqual(result.notes_added, 1)
        self.assertEqual(result.cards_created, 3)
        self.assertEqual(result.pushed_note_ids, [456])
        self.assertTrue(result.sync_completed)

        push_client = FakeAnkiConnectClient.instances[0]
        self.assertIn("tmp-audio.mp3", push_client.stored_media)
        self.assertIn("tmp-image.png", push_client.stored_media)

        add_notes_call = next(call for call in push_client.calls if call[0] == "addNotes")
        payload = add_notes_call[1]["notes"][0]
        self.assertEqual(payload["deckName"], "Korean::Lessons::Greetings")
        self.assertEqual(payload["fields"]["Audio"], "[sound:tmp-audio.mp3]")
        self.assertEqual(payload["fields"]["Image"], "<img src='tmp-image.png'>")
        self.assertEqual(payload["fields"]["EnableListening"], "1")
        self.assertIn("greetings", payload["tags"])

    def test_push_batch_blocks_duplicate_before_add_notes(self) -> None:
        batch = make_batch([generate_note(make_item(korean="일", english="one"))])
        FakeAnkiConnectClient.existing_note_ids = [123]
        FakeAnkiConnectClient.notes_info = [
            {
                "noteId": 123,
                "fields": {
                    "Korean": {"value": "일"},
                    "English": {"value": "one"},
                },
            }
        ]

        with (
            patch("korean_anki.anki_push_service.AnkiConnectClient", FakeAnkiConnectClient),
            patch("korean_anki.anki_queries.AnkiConnectClient", FakeAnkiConnectClient),
        ):
            with self.assertRaisesRegex(RuntimeError, "Duplicate notes already exist"):
                push_batch(batch)

        calls = [call[0] for client in FakeAnkiConnectClient.instances for call in client.calls]
        self.assertNotIn("addNotes", calls)

    def test_plan_push_allows_homographs_with_different_meanings(self) -> None:
        batch = make_batch([generate_note(make_item(korean="일", english="one"))])
        FakeAnkiConnectClient.existing_note_ids = [456]
        FakeAnkiConnectClient.notes_info = [
            {
                "noteId": 456,
                "fields": {
                    "Korean": {"value": "일"},
                    "English": {"value": "day (date)"},
                },
            }
        ]

        with (
            patch("korean_anki.anki_push_service.AnkiConnectClient", FakeAnkiConnectClient),
            patch("korean_anki.anki_queries.AnkiConnectClient", FakeAnkiConnectClient),
        ):
            result = plan_push(batch)

        self.assertTrue(result.can_push)
        self.assertEqual(result.duplicate_notes, [])

        plan_client = FakeAnkiConnectClient.instances[0]
        find_notes_call = next(call for call in plan_client.calls if call[0] == "findNotes")
        self.assertEqual(find_notes_call[1]["query"], f'note:"{ANKI_MODEL_NAME}"')

    def test_push_batch_marks_homographs_as_allowed_duplicates_for_anki(self) -> None:
        batch = make_batch([generate_note(make_item(korean="일", english="one"))])
        FakeAnkiConnectClient.existing_note_ids = [456]
        FakeAnkiConnectClient.notes_info = [
            {
                "noteId": 456,
                "fields": {
                    "Korean": {"value": "일"},
                    "English": {"value": "day (date)"},
                },
            }
        ]
        FakeAnkiConnectClient.add_notes_result = [789]

        with (
            patch("korean_anki.anki_push_service.AnkiConnectClient", FakeAnkiConnectClient),
            patch("korean_anki.anki_queries.AnkiConnectClient", FakeAnkiConnectClient),
        ):
            result = push_batch(batch, sync=False)

        self.assertEqual(result.notes_added, 1)
        self.assertEqual(result.pushed_note_ids, [789])
        self.assertTrue(result.can_push)

        push_client = FakeAnkiConnectClient.instances[0]
        add_notes_call = next(call for call in push_client.calls if call[0] == "addNotes")
        payload = add_notes_call[1]["notes"][0]
        self.assertEqual(payload["fields"]["Korean"], "일")
        self.assertEqual(payload["fields"]["English"], "one")
        self.assertEqual(payload["options"], {"allowDuplicate": True})

    def test_push_batch_sets_reading_speed_enable_fields(self) -> None:
        reading_item = make_item(
            item_id="read-1",
            korean="안녕하세요",
            english="hello",
            notes="Read aloud before revealing meaning.",
            tags=["reading-speed", "read-aloud"],
        ).model_copy(update={"lane": "reading-speed", "skill_tags": ["reading-speed", "read-aloud", "chunked"]})
        batch = make_batch(
            [generate_note(reading_item)],
            metadata=make_metadata(target_deck="Korean::Reading Speed"),
        )
        FakeAnkiConnectClient.add_notes_result = [789]

        with (
            patch("korean_anki.anki_push_service.AnkiConnectClient", FakeAnkiConnectClient),
            patch("korean_anki.anki_queries.AnkiConnectClient", FakeAnkiConnectClient),
        ):
            result = push_batch(batch)

        self.assertEqual(result.notes_added, 1)
        self.assertEqual(result.cards_created, 2)

        push_client = FakeAnkiConnectClient.instances[0]
        add_notes_call = next(call for call in push_client.calls if call[0] == "addNotes")
        payload = add_notes_call[1]["notes"][0]
        self.assertEqual(payload["deckName"], "Korean::Reading Speed")
        self.assertEqual(payload["fields"]["ChunkedKorean"], "안·녕·하·세·요")
        self.assertEqual(payload["fields"]["EnableReadAloud"], "1")
        self.assertEqual(payload["fields"]["EnableChunkedReading"], "1")
        self.assertEqual(payload["fields"]["EnableDecodablePassage"], "")
        self.assertIn("lane:reading-speed", payload["tags"])
        self.assertIn("skill:chunked", payload["tags"])

    def test_sync_lesson_media_downloads_assets_from_anki(self) -> None:
        output_dir = Path("tests/tmp-sync-lesson")
        document = LessonDocument(
            metadata=make_metadata(),
            items=[
                make_item(
                    item_id="item-1",
                    korean="오늘",
                    english="today",
                    audio=None,
                    image=None,
                )
            ],
        )
        FakeAnkiConnectClient.existing_note_ids = [123]
        FakeAnkiConnectClient.notes_info = [
            {
                "noteId": 123,
                "tags": ["type:vocab", "lane:new-vocab", "skill:time"],
                "fields": {
                    "Korean": {"value": "오늘"},
                    "English": {"value": "today"},
                    "Audio": {"value": "[sound:today.mp3]"},
                    "Image": {"value": "<img src='today.png'>"},
                },
            }
        ]
        FakeAnkiConnectClient.media_files = {
            "today.mp3": b"audio-bytes",
            "today.png": b"image-bytes",
        }

        with patch("korean_anki.anki_media_sync.AnkiConnectClient", FakeAnkiConnectClient):
            updated, summary = sync_lesson_media(document, media_dir=output_dir, sync_first=True)

        self.assertEqual(summary.matched_notes, 1)
        self.assertEqual(summary.missing_notes, 0)
        self.assertEqual(summary.audio_downloaded, 1)
        self.assertEqual(summary.image_downloaded, 1)
        self.assertEqual(updated.items[0].audio.path, "tests/tmp-sync-lesson/audio/today.mp3")
        self.assertEqual(updated.items[0].image.path, "tests/tmp-sync-lesson/images/today.png")
        self.assertEqual(Path(updated.items[0].audio.path).read_bytes(), b"audio-bytes")
        self.assertEqual(Path(updated.items[0].image.path).read_bytes(), b"image-bytes")
        self.assertTrue(FakeAnkiConnectClient.instances[0].synced)
        self.addCleanup(lambda: shutil.rmtree(output_dir, ignore_errors=True))

    def test_sync_batch_media_enables_listening_card_when_audio_arrives(self) -> None:
        output_dir = Path("tests/tmp-sync-batch")
        batch = make_batch([generate_note(make_item(korean="오늘", english="today", audio=None, image=None))])
        listening_before = next(card for card in batch.notes[0].cards if card.kind == "listening")
        self.assertFalse(listening_before.approved)

        FakeAnkiConnectClient.existing_note_ids = [123]
        FakeAnkiConnectClient.notes_info = [
            {
                "noteId": 123,
                "tags": ["type:vocab", "lane:new-vocab", "skill:time"],
                "fields": {
                    "Korean": {"value": "오늘"},
                    "English": {"value": "today"},
                    "Audio": {"value": "[sound:today.mp3]"},
                    "Image": {"value": ""},
                },
            }
        ]
        FakeAnkiConnectClient.media_files = {"today.mp3": b"audio-bytes"}

        with patch("korean_anki.anki_media_sync.AnkiConnectClient", FakeAnkiConnectClient):
            updated, summary = sync_batch_media(batch, media_dir=output_dir)

        listening_after = next(card for card in updated.notes[0].cards if card.kind == "listening")
        self.assertEqual(summary.matched_notes, 1)
        self.assertEqual(summary.audio_downloaded, 1)
        self.assertTrue(listening_after.approved)
        self.assertIn("<audio controls", listening_after.front_html)
        self.assertEqual(updated.notes[0].item.audio.path, "tests/tmp-sync-batch/audio/today.mp3")
        self.assertEqual(Path(updated.notes[0].item.audio.path).read_bytes(), b"audio-bytes")
        self.addCleanup(lambda: shutil.rmtree(output_dir, ignore_errors=True))

    def test_ensure_model_upgrades_existing_model_with_reading_speed_fields_and_templates(self) -> None:
        class UpgradeClient(AnkiConnectClient):
            def __init__(self) -> None:
                self.calls: list[tuple[str, dict[str, object]]] = []

            def invoke(self, action: str, **params: object) -> object:
                self.calls.append((action, params))
                if action == "modelNames":
                    return [ANKI_MODEL_NAME]
                if action == "modelFieldNames":
                    return [
                        "Korean",
                        "English",
                        "Pronunciation",
                        "ExampleKo",
                        "ExampleEn",
                        "Notes",
                        "Audio",
                        "Image",
                        "SourceRef",
                        "EnableRecognition",
                        "EnableProduction",
                        "EnableListening",
                        "EnableNumberContext",
                    ]
                if action == "modelTemplates":
                    return {
                        "Recognition": {},
                        "Production": {},
                        "Listening": {},
                        "Number Context": {},
                    }
                return None

        client = UpgradeClient()

        client.ensure_model()

        field_adds = [params["fieldName"] for action, params in client.calls if action == "modelFieldAdd"]
        template_adds = [params["template"]["Name"] for action, params in client.calls if action == "modelTemplateAdd"]
        self.assertEqual(
            field_adds,
            ["ChunkedKorean", "EnableReadAloud", "EnableChunkedReading", "EnableDecodablePassage"],
        )
        self.assertEqual(template_adds, ["Read Aloud", "Chunked Reading", "Decodable Passage"])


if __name__ == "__main__":
    unittest.main()
