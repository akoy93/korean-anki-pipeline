from __future__ import annotations

import json
import unittest
from pathlib import Path


class PortabilityTests(unittest.TestCase):
    def test_tracked_lesson_batches_do_not_reference_untracked_media_files(self) -> None:
        batch_paths = sorted(Path("lessons").glob("*/generated/*.batch.json"))

        for batch_path in batch_paths:
            with self.subTest(batch=str(batch_path)):
                batch = json.loads(batch_path.read_text(encoding="utf-8"))

                for note in batch["notes"]:
                    item = note["item"]
                    self.assertIsNone(item.get("audio"))
                    self.assertIsNone(item.get("image"))

                    listening_cards = [card for card in note["cards"] if card["kind"] == "listening"]
                    self.assertEqual(len(listening_cards), 1)
                    self.assertFalse(listening_cards[0]["approved"])
                    self.assertIn("Audio not generated yet.", listening_cards[0]["front_html"])

                    for card in note["cards"]:
                        self.assertIsNone(card.get("audio_path"))
                        self.assertIsNone(card.get("image_path"))


if __name__ == "__main__":
    unittest.main()
