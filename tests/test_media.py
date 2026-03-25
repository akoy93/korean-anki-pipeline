from __future__ import annotations

import base64
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from korean_anki.media import _audio_asset_is_valid, enrich_audio, enrich_images, enrich_new_vocab_images
from korean_anki.schema import MediaAsset

from support import make_document, make_item


class FakeOpenAI:
    audio_calls: list[dict[str, object]] = []
    image_calls: list[dict[str, object]] = []

    def __init__(self) -> None:
        self.audio = SimpleNamespace(speech=SimpleNamespace(create=self._create_speech))
        self.images = SimpleNamespace(generate=self._generate_image)

    @classmethod
    def reset(cls) -> None:
        cls.audio_calls = []
        cls.image_calls = []

    @classmethod
    def _create_speech(cls, **kwargs: object) -> SimpleNamespace:
        cls.audio_calls.append(kwargs)
        return SimpleNamespace(content=b"mp3-bytes")

    @classmethod
    def _generate_image(cls, **kwargs: object) -> SimpleNamespace:
        cls.image_calls.append(kwargs)
        return SimpleNamespace(data=[SimpleNamespace(b64_json=base64.b64encode(b"png-bytes").decode("ascii"))])


class MediaTests(unittest.TestCase):
    def setUp(self) -> None:
        FakeOpenAI.reset()

    def test_enrich_audio_generates_missing_audio_and_skips_existing_assets(self) -> None:
        existing_audio = MediaAsset(path="preview/public/media/audio/existing.mp3")
        document = make_document(
            [
                make_item(item_id="existing", audio=existing_audio),
                make_item(item_id="missing", korean="감사합니다", english="thank you", audio=None),
            ]
        )

        with (
            patch("korean_anki.media.OpenAI", FakeOpenAI),
            patch("korean_anki.media._audio_asset_is_valid", return_value=True),
        ):
            updated = enrich_audio(document, Path(self._testMethodName))

        self.assertEqual(updated.items[0].audio, existing_audio)
        self.assertEqual(updated.items[1].audio.path, f"{self._testMethodName}/missing.mp3")
        self.assertTrue(Path(updated.items[1].audio.path).exists())
        self.assertEqual(len(FakeOpenAI.audio_calls), 1)
        self.addCleanup(lambda: Path(self._testMethodName).rmdir() if Path(self._testMethodName).exists() else None)
        self.addCleanup(lambda: Path(updated.items[1].audio.path).unlink(missing_ok=True))

    def test_enrich_audio_regenerates_invalid_existing_asset(self) -> None:
        output_dir = Path(self._testMethodName)
        output_dir.mkdir(exist_ok=True)
        existing_path = output_dir / "existing.mp3"
        existing_path.write_bytes(b"old-bytes")
        document = make_document([make_item(item_id="existing", korean="오늘", english="today", audio=MediaAsset(path=str(existing_path)))])

        with (
            patch("korean_anki.media.OpenAI", FakeOpenAI),
            patch("korean_anki.media._audio_asset_is_valid", side_effect=[False, True]),
        ):
            updated = enrich_audio(document, output_dir)

        self.assertEqual(updated.items[0].audio.path, str(existing_path))
        self.assertEqual(existing_path.read_bytes(), b"mp3-bytes")
        self.assertEqual(len(FakeOpenAI.audio_calls), 1)
        self.addCleanup(lambda: output_dir.rmdir() if output_dir.exists() else None)
        self.addCleanup(lambda: existing_path.unlink(missing_ok=True))

    def test_enrich_audio_retries_when_generated_audio_is_invalid(self) -> None:
        output_dir = Path(self._testMethodName)
        document = make_document([make_item(item_id="retry", korean="오늘", english="today", audio=None)])

        with (
            patch("korean_anki.media.OpenAI", FakeOpenAI),
            patch("korean_anki.media._audio_asset_is_valid", side_effect=[False, True]),
        ):
            updated = enrich_audio(document, output_dir)

        self.assertEqual(updated.items[0].audio.path, f"{self._testMethodName}/retry.mp3")
        self.assertEqual(len(FakeOpenAI.audio_calls), 2)
        self.addCleanup(lambda: output_dir.rmdir() if output_dir.exists() else None)
        self.addCleanup(lambda: Path(updated.items[0].audio.path).unlink(missing_ok=True))

    def test_audio_asset_is_valid_rejects_empty_files(self) -> None:
        output_dir = Path(self._testMethodName)
        output_dir.mkdir(exist_ok=True)
        audio_path = output_dir / "empty.mp3"
        audio_path.write_bytes(b"")

        self.assertFalse(_audio_asset_is_valid(audio_path))

        self.addCleanup(lambda: output_dir.rmdir() if output_dir.exists() else None)
        self.addCleanup(lambda: audio_path.unlink(missing_ok=True))

    def test_enrich_images_skips_number_and_grammar_and_uses_model_decision_for_candidates(self) -> None:
        document = make_document(
            [
                make_item(item_id="num-1", item_type="number", korean="일", english="one"),
                make_item(item_id="phrase-1", item_type="phrase", korean="안녕하세요", english="hello"),
                make_item(item_id="phrase-2", item_type="phrase", korean="감사합니다", english="thank you"),
                make_item(item_id="grammar-1", item_type="grammar", korean="은/는", english="topic marker"),
            ]
        )

        output_dir = Path(self._testMethodName)
        with (
            patch("korean_anki.media.OpenAI", FakeOpenAI),
            patch("korean_anki.media.plan_image_generation", return_value={"phrase-1": True, "phrase-2": False}),
        ):
            updated = enrich_images(document, output_dir)

        images_by_id = {item.id: item.image for item in updated.items}
        self.assertIsNone(images_by_id["num-1"])
        self.assertIsNotNone(images_by_id["phrase-1"])
        self.assertIsNone(images_by_id["phrase-2"])
        self.assertIsNone(images_by_id["grammar-1"])
        self.assertEqual(len(FakeOpenAI.image_calls), 1)
        self.assertEqual(FakeOpenAI.image_calls[0]["quality"], "auto")
        self.assertTrue(Path(images_by_id["phrase-1"].path).exists())

        self.addCleanup(lambda: output_dir.rmdir() if output_dir.exists() else None)
        self.addCleanup(lambda: Path(images_by_id["phrase-1"].path).unlink(missing_ok=True))

    def test_enrich_new_vocab_images_generates_an_image_for_every_item(self) -> None:
        document = make_document(
            [
                make_item(
                    item_id="concrete-1",
                    korean="사과",
                    english="apple",
                    image_prompt="A bright red apple on a small table.",
                ),
                make_item(
                    item_id="abstract-1",
                    korean="중요하다",
                    english="important",
                    image_prompt="A child proudly holding a gold star to show something important.",
                ),
            ]
        )

        output_dir = Path(self._testMethodName)
        with patch("korean_anki.media.OpenAI", FakeOpenAI):
            updated = enrich_new_vocab_images(document, output_dir)

        self.assertEqual(len(FakeOpenAI.image_calls), 2)
        self.assertTrue(all(call["quality"] == "low" for call in FakeOpenAI.image_calls))
        self.addCleanup(lambda: output_dir.rmdir() if output_dir.exists() else None)
        for item in updated.items:
            self.assertIsNotNone(item.image)
            self.assertTrue(Path(item.image.path).exists())
            self.assertIn("adult language learner in their 30s", item.image.prompt)
            self.assertIn("warm, playful, and visually engaging", item.image.prompt)
            self.assertIn("depict Korean people", item.image.prompt)
            self.assertIn("No text in the image.", item.image.prompt)
            self.addCleanup(lambda image_path=item.image.path: Path(image_path).unlink(missing_ok=True))


if __name__ == "__main__":
    unittest.main()
