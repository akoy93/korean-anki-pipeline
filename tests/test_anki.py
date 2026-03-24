from __future__ import annotations

import unittest
from pathlib import Path
from unittest.mock import patch

from korean_anki import anki
from korean_anki.cards import generate_note
from korean_anki.schema import MediaAsset

from support import make_batch, make_item, make_metadata


class FakeAnkiConnectClient:
    instances: list["FakeAnkiConnectClient"] = []
    existing_note_ids: list[int] = []
    notes_info: list[dict[str, object]] = []
    add_notes_result: list[int | None] = []

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

    def invoke(self, action: str, **params: object) -> object:
        self.calls.append((action, params))
        if action == "findNotes":
            return self.existing_note_ids
        if action == "notesInfo":
            return self.notes_info
        if action == "modelNames":
            return [anki.ANKI_MODEL_NAME]
        if action == "createDeck":
            return None
        if action == "createModel":
            return None
        if action == "addNotes":
            return self.add_notes_result
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

        with patch("korean_anki.anki.AnkiConnectClient", FakeAnkiConnectClient):
            result = anki.plan_push(batch)

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

        with patch("korean_anki.anki.AnkiConnectClient", FakeAnkiConnectClient):
            result = anki.push_batch(batch)

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

        with patch("korean_anki.anki.AnkiConnectClient", FakeAnkiConnectClient):
            with self.assertRaisesRegex(RuntimeError, "Duplicate notes already exist"):
                anki.push_batch(batch)

        calls = [call[0] for client in FakeAnkiConnectClient.instances for call in client.calls]
        self.assertNotIn("addNotes", calls)


if __name__ == "__main__":
    unittest.main()
