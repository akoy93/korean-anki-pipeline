from __future__ import annotations

import argparse
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from korean_anki import cli
from korean_anki.anki_media_sync import MediaSyncSummary
from korean_anki.schema import PushResult
from korean_anki.sync_media_service import MediaSyncArtifacts

from korean_anki.cards import generate_note

from support import make_batch, make_item, make_transcription


class CliTests(unittest.TestCase):
    def test_command_build_lessons_delegates_to_application_service(self) -> None:
        args = argparse.Namespace(
            input="transcription.json",
            output_dir="lessons/generated",
            pronunciation_model="gpt-5.4-pro",
            skip_pronunciation_fill=True,
        )

        with (
            patch("korean_anki.cli.read_transcription", return_value=make_transcription()) as mock_read,
            patch(
                "korean_anki.cli.build_lesson_documents_from_transcription",
                return_value=[Path("lessons/generated/lesson.json")],
            ) as mock_build,
            redirect_stdout(io.StringIO()),
        ):
            cli._command_build_lessons(args)

        mock_read.assert_called_once_with(Path("transcription.json"))
        mock_build.assert_called_once_with(
            make_transcription(),
            output_dir=Path("lessons/generated"),
            pronunciation_model="gpt-5.4-pro",
            skip_pronunciation_fill=True,
        )

    def test_command_generate_delegates_to_application_service(self) -> None:
        args = argparse.Namespace(
            input="lesson.json",
            output="generated.batch.json",
            with_audio=True,
            with_images=True,
            image_quality="high",
            media_dir="data/media",
            project_root=".",
            anki_url="http://127.0.0.1:8765",
        )

        with patch("korean_anki.cli.generate_batch_from_lesson_file") as mock_generate:
            cli._command_generate(args)

        mock_generate.assert_called_once_with(
            input_path=Path("lesson.json"),
            output_path=Path("generated.batch.json"),
            media_dir=Path("data/media"),
            project_root=Path("."),
            anki_url="http://127.0.0.1:8765",
            with_audio=True,
            with_images=True,
            image_quality="high",
        )

    def test_command_generate_new_vocab_delegates_to_application_service(self) -> None:
        args = argparse.Namespace(
            lesson_id="new-vocab-2026-03-26",
            title="Weather Basics",
            lesson_date="2026-03-26",
            output="data/generated/weather.batch.json",
            count=12,
            gap_ratio=0.7,
            target_deck="Korean::New Vocab",
            lesson_context="lessons/context.json",
            with_audio=True,
            image_quality="low",
            media_dir="data/media",
            project_root=".",
            anki_url="http://127.0.0.1:8765",
            model="gpt-5.4",
        )

        with patch("korean_anki.cli.generate_new_vocab_batch") as mock_generate:
            cli._command_generate_new_vocab(args)

        mock_generate.assert_called_once_with(
            project_root=Path("."),
            output_path=Path("data/generated/weather.batch.json"),
            lesson_id="new-vocab-2026-03-26",
            title="Weather Basics",
            lesson_date=cli.date.fromisoformat("2026-03-26"),
            count=12,
            gap_ratio=0.7,
            target_deck="Korean::New Vocab",
            lesson_context_path=Path("lessons/context.json"),
            media_dir=Path("data/media"),
            anki_url="http://127.0.0.1:8765",
            with_audio=True,
            image_quality="low",
            model="gpt-5.4",
        )

    def test_command_push_delegates_to_application_service(self) -> None:
        batch = make_batch([generate_note(make_item())])
        result = PushResult(
            deck_name="Korean::Lessons::Basics",
            approved_notes=0,
            approved_cards=0,
            dry_run=False,
            can_push=True,
        )

        with tempfile.TemporaryDirectory() as temp_dir:
            input_path = Path(temp_dir) / "sample.batch.json"
            input_path.write_text(batch.model_dump_json(indent=2), encoding="utf-8")
            args = argparse.Namespace(
                input=str(input_path),
                deck=None,
                anki_url="http://127.0.0.1:8765",
                no_sync=False,
            )

            with (
                patch("korean_anki.cli.handle_push_request", return_value=result) as mock_handle_push,
                redirect_stdout(io.StringIO()),
            ):
                cli._command_push(args)

        request = mock_handle_push.call_args.args[0]
        self.assertEqual(request.batch, batch)
        self.assertFalse(request.dry_run)
        self.assertIsNone(request.deck_name)
        self.assertEqual(request.anki_url, "http://127.0.0.1:8765")
        self.assertTrue(request.sync)

    def test_command_sync_media_delegates_to_application_service(self) -> None:
        args = argparse.Namespace(
            input="data/generated/sample.batch.json",
            output=None,
            media_dir="data/media",
            anki_url="http://127.0.0.1:8765",
            sync_first=True,
        )

        with (
            patch(
                "korean_anki.cli.sync_media_file",
                return_value=MediaSyncArtifacts(
                    output_path=Path("data/generated/sample.synced.batch.json"),
                    summary=MediaSyncSummary(matched_notes=1, audio_downloaded=1),
                ),
            ) as mock_sync,
            redirect_stdout(io.StringIO()),
        ):
            cli._command_sync_media(args)

        mock_sync.assert_called_once_with(
            input_path=Path("data/generated/sample.batch.json"),
            output_path=Path("data/generated/sample.synced.batch.json"),
            media_dir=Path("data/media"),
            project_root=Path.cwd().resolve(),
            anki_url="http://127.0.0.1:8765",
            sync_first=True,
        )


if __name__ == "__main__":
    unittest.main()
