from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .batch_generation_service import generate_batch_from_lesson_file
from .llm_service import generate_pronunciations, transcribe_sources
from .schema import LessonTranscription, RawSourceAsset
from .service_support import unique_lesson_root
from .stages import build_lesson_documents, qa_transcription, write_lesson_documents


@dataclass(frozen=True)
class LessonGenerationArtifacts:
    lesson_root: Path
    transcription_path: Path
    qa_report_path: Path
    lesson_paths: list[Path]
    batch_paths: list[Path]


def build_lesson_documents_from_transcription(
    transcription: LessonTranscription,
    *,
    output_dir: Path,
    pronunciation_model: str = "gpt-5.4",
    skip_pronunciation_fill: bool = False,
) -> list[Path]:
    pronunciation_lookup: dict[str, str] = {}
    if not skip_pronunciation_fill:
        missing_pronunciations = [
            entry.korean
            for section in transcription.sections
            for entry in section.entries
            if entry.pronunciation is None
        ]
        pronunciation_lookup = generate_pronunciations(
            missing_pronunciations,
            model=pronunciation_model,
        )

    documents = build_lesson_documents(transcription, pronunciation_lookup=pronunciation_lookup)
    return write_lesson_documents(documents, output_dir)


def generate_lesson_batches_from_sources(
    *,
    project_root: Path,
    lesson_root: Path | None = None,
    lesson_date: str,
    title: str,
    topic: str,
    source_summary: str,
    raw_sources: list[RawSourceAsset],
    with_audio: bool = True,
    transcription_model: str = "gpt-5.4",
    pronunciation_model: str = "gpt-5.4",
    anki_url: str = "http://127.0.0.1:8765",
) -> LessonGenerationArtifacts:
    lesson_root = lesson_root or unique_lesson_root(project_root, lesson_date, topic)
    generated_dir = lesson_root / "generated"
    generated_dir.mkdir(parents=True, exist_ok=True)

    lesson_slug = lesson_root.name
    transcription = transcribe_sources(
        lesson_id=f"italki-{lesson_slug}",
        title=title,
        lesson_date=lesson_date,
        source_summary=source_summary,
        raw_sources=raw_sources,
        model=transcription_model,
    )
    transcription_path = lesson_root / "transcription.json"
    transcription_path.write_text(transcription.model_dump_json(indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    qa_report = qa_transcription(transcription)
    qa_report_path = lesson_root / "qa-report.json"
    qa_report_path.write_text(qa_report.model_dump_json(indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    if not qa_report.passed:
        raise ValueError("Lesson QA failed.")

    lesson_paths = build_lesson_documents_from_transcription(
        transcription,
        output_dir=generated_dir,
        pronunciation_model=pronunciation_model,
    )
    batch_paths: list[Path] = []
    for lesson_path in lesson_paths:
        artifacts = generate_batch_from_lesson_file(
            input_path=lesson_path,
            output_path=lesson_path.with_suffix(".batch.json"),
            media_dir=project_root / "data/media",
            project_root=project_root,
            anki_url=anki_url,
            with_audio=with_audio,
        )
        batch_paths.append(artifacts.output_path)

    return LessonGenerationArtifacts(
        lesson_root=lesson_root,
        transcription_path=transcription_path,
        qa_report_path=qa_report_path,
        lesson_paths=lesson_paths,
        batch_paths=batch_paths,
    )
