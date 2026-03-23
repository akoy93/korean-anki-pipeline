from __future__ import annotations

import argparse
from datetime import date
from pathlib import Path

from dotenv import load_dotenv

from .anki import DEFAULT_DECK, push_batch
from .cards import generate_batch
from .llm import extract_lesson, read_lesson, read_transcription, transcribe_sources, write_json
from .media import enrich_audio, enrich_images
from .schema import CardBatch, ExtractionRequest, RawSourceAsset
from .stages import build_lesson_documents, qa_transcription, write_lesson_documents


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(prog="korean-anki")
    subparsers = parser.add_subparsers(dest="command", required=True)

    extract = subparsers.add_parser("extract", help="Extract lesson material into normalized JSON.")
    extract.add_argument("--lesson-id", required=True)
    extract.add_argument("--title", required=True)
    extract.add_argument("--topic", required=True)
    extract.add_argument("--lesson-date", default=date.today().isoformat())
    extract.add_argument("--source-description", required=True)
    extract.add_argument("--item-type-default", choices=["vocab", "phrase", "grammar", "dialogue", "number"], default="vocab")
    extract.add_argument("--text")
    extract.add_argument("--text-file")
    extract.add_argument("--image")
    extract.add_argument("--output", required=True)
    extract.add_argument("--model", default="gpt-5.4")
    extract.add_argument("--qa-model", default="gpt-5.4-pro")
    extract.add_argument("--run-qa", action="store_true")

    transcribe = subparsers.add_parser("transcribe", help="Stage 1: transcribe raw sources into a faithful structured source document.")
    transcribe.add_argument("--lesson-id", required=True)
    transcribe.add_argument("--title", required=True)
    transcribe.add_argument("--lesson-date", default=date.today().isoformat())
    transcribe.add_argument("--source-summary", required=True)
    transcribe.add_argument("--image", action="append", default=[])
    transcribe.add_argument("--notes-file", action="append", default=[])
    transcribe.add_argument("--output", required=True)
    transcribe.add_argument("--model", default="gpt-5.4")

    build_lessons = subparsers.add_parser("build-lessons", help="Stage 2: build one lesson JSON per transcribed section.")
    build_lessons.add_argument("--input", required=True)
    build_lessons.add_argument("--output-dir", required=True)

    qa = subparsers.add_parser("qa", help="Stage 3: run deterministic QA checks on a transcription.")
    qa.add_argument("--input", required=True)
    qa.add_argument("--output", required=True)

    generate = subparsers.add_parser("generate", help="Generate a reviewable card batch from lesson JSON.")
    generate.add_argument("--input", required=True)
    generate.add_argument("--output", required=True)
    generate.add_argument("--with-audio", action="store_true")
    generate.add_argument("--with-images", action="store_true")
    generate.add_argument("--media-dir", default="data/media")

    push = subparsers.add_parser("push", help="Push approved cards to Anki Desktop via AnkiConnect.")
    push.add_argument("--input", required=True)
    push.add_argument("--deck", default=None)
    push.add_argument("--anki-url", default="http://127.0.0.1:8765")
    push.add_argument("--no-sync", action="store_true")

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
    documents = build_lesson_documents(transcription)
    written = write_lesson_documents(documents, Path(args.output_dir))
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
    document = read_lesson(Path(args.input))
    media_dir = Path(args.media_dir)

    if args.with_audio:
        document = enrich_audio(document, media_dir / "audio")
    if args.with_images:
        document = enrich_images(document, media_dir / "images")

    batch = generate_batch(document)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(batch.model_dump_json(indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def _command_push(args: argparse.Namespace) -> None:
    batch = CardBatch.model_validate_json(Path(args.input).read_text(encoding="utf-8"))
    deck_name = args.deck if args.deck is not None else batch.metadata.target_deck or DEFAULT_DECK
    note_ids = push_batch(
        batch,
        deck_name=deck_name,
        anki_url=args.anki_url,
        sync=not args.no_sync,
    )
    print(f"Pushed {len(note_ids)} notes to Anki: {note_ids}")


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
    if args.command == "push":
        _command_push(args)
        return

    raise SystemExit(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
