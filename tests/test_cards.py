from __future__ import annotations

import unittest

from korean_anki.cards import generate_batch, generate_note
from korean_anki.schema import ExampleSentence, MediaAsset, PriorNote, StudyState

from support import make_document, make_item


class CardGenerationTests(unittest.TestCase):
    def test_number_items_get_four_cards_and_listening_requires_audio(self) -> None:
        number_item = make_item(
            item_id="num-1",
            item_type="number",
            korean="일",
            english="one",
            pronunciation="il",
            examples=[ExampleSentence(korean="일 원", english="one won")],
            audio=MediaAsset(path="preview/public/media/audio/num-1.mp3"),
        )

        note = generate_note(number_item)

        self.assertEqual([card.kind for card in note.cards], ["recognition", "production", "listening", "number-context"])
        self.assertTrue(all(card.approved for card in note.cards))
        listening = next(card for card in note.cards if card.kind == "listening")
        self.assertIn("<audio controls", listening.front_html)
        self.assertIn("il", listening.back_html)
        self.assertIn("Source:", listening.back_html)

    def test_vocab_items_get_three_cards_and_missing_audio_disables_listening(self) -> None:
        vocab_item = make_item(item_id="vocab-1", item_type="vocab", audio=None, image=None)

        note = generate_note(vocab_item)

        self.assertEqual([card.kind for card in note.cards], ["recognition", "production", "listening"])
        listening = next(card for card in note.cards if card.kind == "listening")
        self.assertFalse(listening.approved)
        self.assertIn("Audio not generated yet.", listening.front_html)

    def test_generate_batch_preserves_metadata_and_creates_one_note_per_item(self) -> None:
        document = make_document(
            [
                make_item(item_id="item-1"),
                make_item(item_id="item-2", korean="감사합니다", english="thank you"),
            ]
        )

        batch = generate_batch(document)

        self.assertEqual(batch.metadata.lesson_id, document.metadata.lesson_id)
        self.assertEqual([note.item.id for note in batch.notes], ["item-1", "item-2"])

    def test_generate_note_marks_exact_duplicate_as_blocked_and_near_duplicate_as_warning(self) -> None:
        prior = PriorNote(
            note_key="vocab:안녕하세요:hello",
            korean="안녕하세요",
            english="hello",
            item_type="vocab",
            lane="lesson",
            skill_tags=["greetings"],
            source="lessons/2026-03-23-hello/generated/hello.batch.json",
            existing_note_id=42,
        )

        exact_item = make_item(item_id="exact-1", korean="안녕하세요", english="hello", tags=["greetings"])
        exact_note = generate_note(exact_item, prior_notes=[prior])

        self.assertEqual(exact_note.duplicate_status, "exact-duplicate")
        self.assertFalse(exact_note.approved)
        self.assertTrue(all(not card.approved for card in exact_note.cards))
        self.assertEqual(exact_note.duplicate_note_id, 42)
        self.assertIn("Exact duplicate", exact_note.inclusion_reason)
        self.assertEqual(exact_note.note_key, "vocab:안녕하세요:hello")

        near_item = make_item(item_id="near-1", korean="안녕하세요", english="hi", tags=["greetings"])
        near_note = generate_note(near_item, prior_notes=[prior])

        self.assertEqual(near_note.duplicate_status, "near-duplicate")
        self.assertTrue(near_note.approved)
        self.assertIn("Near-duplicate", near_note.inclusion_reason)
        self.assertEqual(near_note.duplicate_note_key, prior.note_key)

    def test_generate_batch_uses_study_state_history(self) -> None:
        existing = make_item(item_id="item-old", korean="안녕하세요", english="hello")
        state = StudyState(
            generated_notes=[
                PriorNote(
                    note_key="vocab:안녕하세요:hello",
                    korean=existing.korean,
                    english=existing.english,
                    item_type="vocab",
                    source="prior.batch.json",
                )
            ]
        )
        document = make_document([make_item(item_id="item-new", korean="안녕하세요", english="hello")])

        batch = generate_batch(document, study_state=state)

        self.assertEqual(batch.notes[0].duplicate_status, "exact-duplicate")
        self.assertFalse(batch.notes[0].approved)

    def test_reading_speed_items_use_reading_cards_and_skip_duplicate_blocking(self) -> None:
        prior = PriorNote(
            note_key="vocab:안녕하세요:hello",
            korean="안녕하세요",
            english="hello",
            item_type="vocab",
            lane="lesson",
            source="prior.batch.json",
        )
        reading_item = make_item(
            item_id="read-1",
            korean="안녕하세요",
            english="hello",
            tags=["reading-speed", "read-aloud"],
        ).model_copy(update={"lane": "reading-speed", "skill_tags": ["reading-speed", "read-aloud", "chunked"]})

        note = generate_note(reading_item, prior_notes=[prior])

        self.assertEqual(note.lane, "reading-speed")
        self.assertEqual(note.duplicate_status, "new")
        self.assertTrue(note.approved)
        self.assertEqual([card.kind for card in note.cards], ["read-aloud", "chunked-reading"])
        chunked = next(card for card in note.cards if card.kind == "chunked-reading")
        self.assertIn("안·녕·하·세·요", chunked.front_html)

    def test_reading_speed_history_does_not_block_lesson_cards(self) -> None:
        prior = PriorNote(
            note_key="number:일:one",
            korean="일",
            english="one",
            item_type="number",
            lane="reading-speed",
            skill_tags=["reading-speed", "read-aloud"],
            source="data/generated/reading-speed-2026-03-23.batch.json",
        )
        lesson_item = make_item(
            item_id="sino-1",
            item_type="number",
            korean="일",
            english="one",
            tags=["numbers", "sino-korean"],
        ).model_copy(update={"lane": "lesson", "skill_tags": ["numbers", "sino-korean"]})

        note = generate_note(lesson_item, prior_notes=[prior])

        self.assertEqual(note.duplicate_status, "new")
        self.assertTrue(note.approved)
        self.assertTrue(all(card.approved for card in note.cards if card.kind != "listening"))


if __name__ == "__main__":
    unittest.main()
