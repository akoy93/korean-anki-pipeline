from __future__ import annotations

import unittest

from korean_anki.cards import generate_batch, generate_note
from korean_anki.schema import ExampleSentence, MediaAsset

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


if __name__ == "__main__":
    unittest.main()
