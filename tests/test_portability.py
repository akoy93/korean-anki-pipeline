from __future__ import annotations

import json
import subprocess
import unittest
from pathlib import Path


class PortabilityTests(unittest.TestCase):
    def test_tracked_lesson_batches_reference_only_tracked_media_files(self) -> None:
        tracked_files = subprocess.run(
            ["git", "ls-files"],
            check=True,
            capture_output=True,
            text=True,
        ).stdout.splitlines()
        batch_paths = [
            Path(path)
            for path in tracked_files
            if path.endswith(".batch.json")
            and (("/generated/" in path and path.startswith("lessons/")) or path.startswith("data/generated/"))
        ]

        for batch_path in batch_paths:
            with self.subTest(batch=str(batch_path)):
                batch = json.loads(batch_path.read_text(encoding="utf-8"))

                for note in batch["notes"]:
                    item = note["item"]
                    listening_cards = [card for card in note["cards"] if card["kind"] == "listening"]
                    self.assertEqual(len(listening_cards), 1)

                    audio = item.get("audio")
                    if audio is None:
                        self.assertFalse(listening_cards[0]["approved"])
                        self.assertIn("Audio not generated yet.", listening_cards[0]["front_html"])
                    else:
                        audio_path = Path(audio["path"])
                        self.assertTrue(audio_path.is_relative_to(Path("data/media")), f"Audio must live under data/media: {audio_path}")
                        self.assertTrue(audio_path.exists(), f"Missing audio file: {audio_path}")
                        tracked = subprocess.run(
                            ["git", "ls-files", "--error-unmatch", str(audio_path)],
                            check=False,
                            capture_output=True,
                            text=True,
                        )
                        self.assertEqual(tracked.returncode, 0, f"Untracked audio file: {audio_path}")
                        ignored = subprocess.run(
                            ["git", "check-ignore", str(audio_path)],
                            check=False,
                            capture_output=True,
                            text=True,
                        )
                        self.assertNotEqual(ignored.returncode, 0, f"Ignored audio file will not show up in git status: {audio_path}")

                    image = item.get("image")
                    if image is not None:
                        image_path = Path(image["path"])
                        self.assertTrue(image_path.is_relative_to(Path("data/media")), f"Image must live under data/media: {image_path}")
                        self.assertTrue(image_path.exists(), f"Missing image file: {image_path}")
                        tracked = subprocess.run(
                            ["git", "ls-files", "--error-unmatch", str(image_path)],
                            check=False,
                            capture_output=True,
                            text=True,
                        )
                        self.assertEqual(tracked.returncode, 0, f"Untracked image file: {image_path}")
                        ignored = subprocess.run(
                            ["git", "check-ignore", str(image_path)],
                            check=False,
                            capture_output=True,
                            text=True,
                        )
                        self.assertNotEqual(ignored.returncode, 0, f"Ignored image file will not show up in git status: {image_path}")

                    for card in note["cards"]:
                        card_audio_path = card.get("audio_path")
                        if card_audio_path is not None:
                            self.assertTrue(Path(card_audio_path).exists(), f"Missing card audio file: {card_audio_path}")

                        card_image_path = card.get("image_path")
                        if card_image_path is not None:
                            self.assertTrue(Path(card_image_path).exists(), f"Missing card image file: {card_image_path}")


if __name__ == "__main__":
    unittest.main()
