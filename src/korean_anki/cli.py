from __future__ import annotations

import argparse
import json
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from .batch_generation_service import (
    generate_batch_from_lesson_file,
    generate_reading_speed_batch,
)
from .lesson_generation_service import build_lesson_documents_from_transcription
from .new_vocab_generation_service import generate_new_vocab_batch
from .path_policy import default_synced_output_path
from .push_workflow_service import handle_push_request
from .sync_media_service import sync_media_file
from .http_api import run_server
from .lesson_io import read_transcription, write_json
from .llm_service import extract_lesson, transcribe_sources
from .schema import CardBatch, ExtractionRequest, PushRequest, RawSourceAsset
from .settings import (
    DEFAULT_ANKI_URL,
    DEFAULT_EXTRACTION_ITEM_TYPE,
    DEFAULT_GENERATE_IMAGE_QUALITY,
    DEFAULT_LLM_MODEL,
    DEFAULT_MEDIA_DIR,
    DEFAULT_NEW_VOCAB_COUNT,
    DEFAULT_NEW_VOCAB_GAP_RATIO,
    DEFAULT_NEW_VOCAB_IMAGE_QUALITY,
    DEFAULT_NEW_VOCAB_TARGET_DECK,
    DEFAULT_NEW_VOCAB_TITLE,
    DEFAULT_PREVIEW_HOST,
    DEFAULT_PREVIEW_PORT,
    DEFAULT_QA_MODEL,
    DEFAULT_READING_SPEED_MAX_CHUNKED,
    DEFAULT_READING_SPEED_MAX_READ_ALOUD,
    DEFAULT_READING_SPEED_PASSAGE_WORD_COUNT,
    DEFAULT_READING_SPEED_SOURCE_DESCRIPTION,
    DEFAULT_READING_SPEED_TARGET_DECK,
    DEFAULT_READING_SPEED_TOPIC,
)
from .stages import qa_transcription


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="korean-anki")
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract = subparsers.add_parser("extract", help="Extract lesson material into normalized JSON.")
    extract.add_argument("--lesson-id", required=True)
    extract.add_argument("--title", required=True)
    extract.add_argument("--topic", required=True)
    extract.add_argument("--lesson-date", default=date.today().isoformat())
    extract.add_argument("--source-description", required=True)
    extract.add_argument("--item-type-default", choices=["vocab", "phrase", "grammar", "dialogue", "number"], default=DEFAULT_EXTRACTION_ITEM_TYPE)
    extract.add_argument("--text")
    extract.add_argument("--text-file")
    extract.add_argument("--image")
    extract.add_argument("--output", required=True)
    extract.add_argument("--model", default=DEFAULT_LLM_MODEL)
    extract.add_argument("--qa-model", default=DEFAULT_QA_MODEL)
    extract.add_argument("--run-qa", action="store_true")

    transcribe = subparsers.add_parser("transcribe", help="Stage 1: transcribe raw sources into a faithful structured source document.")
    transcribe.add_argument("--lesson-id", required=True)
    transcribe.add_argument("--title", required=True)
    transcribe.add_argument("--lesson-date", default=date.today().isoformat())
    transcribe.add_argument("--source-summary", required=True)
    transcribe.add_argument("--image", action="append", default=[])
    transcribe.add_argument("--notes-file", action="append", default=[])
    transcribe.add_argument("--output", required=True)
    transcribe.add_argument("--model", default=DEFAULT_LLM_MODEL)

    build_lessons = subparsers.add_parser("build-lessons", help="Stage 2: build one lesson JSON per transcribed section.")
    build_lessons.add_argument("--input", required=True)
    build_lessons.add_argument("--output-dir", required=True)
    build_lessons.add_argument("--pronunciation-model", default=DEFAULT_LLM_MODEL)
    build_lessons.add_argument("--skip-pronunciation-fill", action="store_true")

    qa = subparsers.add_parser("qa", help="Stage 3: run deterministic QA checks on a transcription.")
    qa.add_argument("--input", required=True)
    qa.add_argument("--output", required=True)

    generate = subparsers.add_parser("generate", help="Generate a reviewable card batch from lesson JSON.")
    generate.add_argument("--input", required=True)
    generate.add_argument("--output", required=True)
    generate.add_argument("--with-audio", action="store_true")
    generate.add_argument("--with-images", action="store_true")
    generate.add_argument(
        "--image-quality",
        choices=["auto", "low", "medium", "high"],
        default=DEFAULT_GENERATE_IMAGE_QUALITY,
    )
    generate.add_argument("--media-dir", default=DEFAULT_MEDIA_DIR)
    generate.add_argument("--project-root", default=".")
    generate.add_argument("--anki-url", default=DEFAULT_ANKI_URL)

    reading_speed = subparsers.add_parser(
        "generate-reading-speed",
        help="Generate a reading-speed batch from the known-word bank in study state.",
    )
    reading_speed.add_argument("--lesson-id", required=True)
    reading_speed.add_argument("--title", required=True)
    reading_speed.add_argument("--topic", default=DEFAULT_READING_SPEED_TOPIC)
    reading_speed.add_argument("--lesson-date", default=date.today().isoformat())
    reading_speed.add_argument(
        "--source-description",
        default=DEFAULT_READING_SPEED_SOURCE_DESCRIPTION,
    )
    reading_speed.add_argument("--target-deck", default=DEFAULT_READING_SPEED_TARGET_DECK)
    reading_speed.add_argument("--output", required=True)
    reading_speed.add_argument("--with-audio", action="store_true")
    reading_speed.add_argument("--media-dir", default=DEFAULT_MEDIA_DIR)
    reading_speed.add_argument("--project-root", default=".")
    reading_speed.add_argument("--anki-url", default=DEFAULT_ANKI_URL)
    reading_speed.add_argument("--max-read-aloud", type=int, default=DEFAULT_READING_SPEED_MAX_READ_ALOUD)
    reading_speed.add_argument("--max-chunked", type=int, default=DEFAULT_READING_SPEED_MAX_CHUNKED)
    reading_speed.add_argument("--passage-word-count", type=int, default=DEFAULT_READING_SPEED_PASSAGE_WORD_COUNT)

    new_vocab = subparsers.add_parser(
        "generate-new-vocab",
        help="Generate a supplemental new-vocab batch from LLM proposals plus local guardrails.",
    )
    new_vocab.add_argument("--lesson-id", default=f"new-vocab-{date.today().isoformat()}")
    new_vocab.add_argument("--title", default=DEFAULT_NEW_VOCAB_TITLE)
    new_vocab.add_argument("--lesson-date", default=date.today().isoformat())
    new_vocab.add_argument("--output", required=True)
    new_vocab.add_argument("--count", type=int, default=DEFAULT_NEW_VOCAB_COUNT)
    new_vocab.add_argument("--gap-ratio", type=float, default=DEFAULT_NEW_VOCAB_GAP_RATIO)
    new_vocab.add_argument("--target-deck", default=DEFAULT_NEW_VOCAB_TARGET_DECK)
    new_vocab.add_argument("--lesson-context", default=None)
    new_vocab.add_argument("--with-audio", action="store_true")
    new_vocab.add_argument(
        "--image-quality",
        choices=["auto", "low", "medium", "high"],
        default=DEFAULT_NEW_VOCAB_IMAGE_QUALITY,
    )
    new_vocab.add_argument("--media-dir", default=DEFAULT_MEDIA_DIR)
    new_vocab.add_argument("--project-root", default=".")
    new_vocab.add_argument("--anki-url", default=DEFAULT_ANKI_URL)
    new_vocab.add_argument("--model", default=DEFAULT_LLM_MODEL)

    push = subparsers.add_parser("push", help="Push approved cards to Anki Desktop via AnkiConnect.")
    push.add_argument("--input", required=True)
    push.add_argument("--deck", default=None)
    push.add_argument("--anki-url", default=DEFAULT_ANKI_URL)
    push.add_argument("--no-sync", action="store_true")

    sync_media = subparsers.add_parser(
        "sync-media",
        help="Hydrate local lesson or batch media from existing Anki notes via AnkiConnect.",
    )
    sync_media.add_argument("--input", required=True)
    sync_media.add_argument("--output", default=None)
    sync_media.add_argument("--media-dir", default=DEFAULT_MEDIA_DIR)
    sync_media.add_argument("--anki-url", default=DEFAULT_ANKI_URL)
    sync_media.add_argument("--sync-first", action="store_true")

    serve = subparsers.add_parser("serve", help="Run the local-only Python HTTP service for preview push actions.")
    serve.add_argument("--host", default=DEFAULT_PREVIEW_HOST)
    serve.add_argument("--port", type=int, default=DEFAULT_PREVIEW_PORT)

    return parser.parse_args()


def _command_extract(args: argparse.Namespace) -> None:
    text = args.text
    if args.text_file is not None:
        text = Path(args.text_file).read_text(encoding="utf-8")
    if text is None and args.image is None:
        raise SystemExit("Provide --text, --text-file, or --image.")

    request = ExtractionRequest(
        lesson_id=args.lesson_id,
        title=args.title,
        topic=args.topic,
        lesson_date=date.fromisoformat(args.lesson_date),
        source_description=args.source_description,
        item_type_default=args.item_type_default,
        text=text,
        image_path=args.image,
        model=args.model,
        qa_model=args.qa_model,
        run_qa=args.run_qa,
    )
    document = extract_lesson(request)
    write_json(document, Path(args.output))


def _command_transcribe(args: argparse.Namespace) -> None:
    raw_sources: list[RawSourceAsset] = [
        RawSourceAsset(kind="image", path=image_path, description="Lesson image")
        for image_path in args.image
    ]
    raw_sources.extend(
        RawSourceAsset(kind="text", path=notes_path, description="User-provided raw notes")
        for notes_path in args.notes_file
    )
    if not raw_sources:
        raise SystemExit("Provide at least one --image or --notes-file.")

    transcription = transcribe_sources(
        lesson_id=args.lesson_id,
        title=args.title,
        lesson_date=args.lesson_date,
        source_summary=args.source_summary,
        raw_sources=raw_sources,
        model=args.model,
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(transcription.model_dump_json(indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _command_build_lessons(args: argparse.Namespace) -> None:
    transcription = read_transcription(Path(args.input))
    written = build_lesson_documents_from_transcription(
        transcription,
        output_dir=Path(args.output_dir),
        pronunciation_model=args.pronunciation_model,
        skip_pronunciation_fill=args.skip_pronunciation_fill,
    )
    print("\n".join(str(path) for path in written))


def _command_qa(args: argparse.Namespace) -> None:
    transcription = read_transcription(Path(args.input))
    report = qa_transcription(transcription)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report.model_dump_json(indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    print(report.model_dump_json(indent=2, ensure_ascii=False))
    if not report.passed:
        raise SystemExit(1)


def _command_generate(args: argparse.Namespace) -> None:
    generate_batch_from_lesson_file(
        input_path=Path(args.input),
        output_path=Path(args.output),
        media_dir=Path(args.media_dir),
        project_root=Path(args.project_root),
        anki_url=args.anki_url,
        with_audio=args.with_audio,
        with_images=args.with_images,
        image_quality=args.image_quality,
    )


def _command_generate_reading_speed(args: argparse.Namespace) -> None:
    generate_reading_speed_batch(
        project_root=Path(args.project_root),
        output_path=Path(args.output),
        lesson_id=args.lesson_id,
        title=args.title,
        topic=args.topic,
        lesson_date=date.fromisoformat(args.lesson_date),
        source_description=args.source_description,
        target_deck=args.target_deck,
        media_dir=Path(args.media_dir),
        anki_url=args.anki_url,
        with_audio=args.with_audio,
        max_read_aloud=args.max_read_aloud,
        max_chunked=args.max_chunked,
        passage_word_count=args.passage_word_count,
    )


def _command_generate_new_vocab(args: argparse.Namespace) -> None:
    generate_new_vocab_batch(
        project_root=Path(args.project_root),
        output_path=Path(args.output),
        lesson_id=args.lesson_id,
        title=args.title,
        lesson_date=date.fromisoformat(args.lesson_date),
        count=args.count,
        gap_ratio=args.gap_ratio,
        target_deck=args.target_deck,
        lesson_context_path=Path(args.lesson_context) if args.lesson_context is not None else None,
        media_dir=Path(args.media_dir),
        anki_url=args.anki_url,
        with_audio=args.with_audio,
        image_quality=args.image_quality,
        model=args.model,
    )


def _command_push(args: argparse.Namespace) -> None:
    batch = CardBatch.model_validate_json(Path(args.input).read_text(encoding="utf-8"))
    result = handle_push_request(
        PushRequest(
            batch=batch,
            dry_run=False,
            deck_name=args.deck,
            anki_url=args.anki_url,
            sync=not args.no_sync,
        )
    )
    print(result.model_dump_json(indent=2, ensure_ascii=False))


def _command_sync_media(args: argparse.Namespace) -> None:
    input_path = Path(args.input)
    result = sync_media_file(
        input_path=input_path,
        output_path=Path(args.output) if args.output is not None else default_synced_output_path(input_path),
        media_dir=Path(args.media_dir),
        project_root=Path.cwd().resolve(),
        anki_url=args.anki_url,
        sync_first=args.sync_first,
    )
    print(json.dumps({"output_path": str(result.output_path), **result.summary.__dict__}, indent=2))


def main() -> None:
    load_dotenv(override=True)
    args = _parse_args()
    if args.command == "extract":
        _command_extract(args)
        return
    if args.command == "transcribe":
        _command_transcribe(args)
        return
    if args.command == "build-lessons":
        _command_build_lessons(args)
        return
    if args.command == "qa":
        _command_qa(args)
        return
    if args.command == "generate":
        _command_generate(args)
        return
    if args.command == "generate-reading-speed":
        _command_generate_reading_speed(args)
        return
    if args.command == "generate-new-vocab":
        _command_generate_new_vocab(args)
        return
    if args.command == "push":
        _command_push(args)
        return
    if args.command == "sync-media":
        _command_sync_media(args)
        return
    if args.command == "serve":
        run_server(host=args.host, port=args.port)
        return

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
