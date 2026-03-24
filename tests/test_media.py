from __future__ import annotations

import base64
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from korean_anki.media import enrich_audio, enrich_images
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

        with patch("korean_anki.media.OpenAI", FakeOpenAI):
            updated = enrich_audio(document, Path(self._testMethodName))

        self.assertEqual(updated.items[0].audio, existing_audio)
        self.assertEqual(updated.items[1].audio.path, f"{self._testMethodName}/missing.mp3")
        self.assertTrue(Path(updated.items[1].audio.path).exists())
        self.assertEqual(len(FakeOpenAI.audio_calls), 1)
        self.addCleanup(lambda: Path(self._testMethodName).rmdir() if Path(self._testMethodName).exists() else None)
        self.addCleanup(lambda: Path(updated.items[1].audio.path).unlink(missing_ok=True))

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
        self.assertTrue(Path(images_by_id["phrase-1"].path).exists())

        self.addCleanup(lambda: output_dir.rmdir() if output_dir.exists() else None)
        self.addCleanup(lambda: Path(images_by_id["phrase-1"].path).unlink(missing_ok=True))


if __name__ == "__main__":
    unittest.main()
