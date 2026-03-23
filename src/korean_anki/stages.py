from __future__ import annotations

from collections import Counter
from pathlib import Path

from .schema import (
    ExampleSentence,
    ItemType,
    LessonDocument,
    LessonItem,
    LessonMetadata,
    LessonTranscription,
    QaIssue,
    QaReport,
    TranscriptionEntry,
)


def _default_deck(transcription: LessonTranscription, section_title: str) -> str:
    normalized = section_title.replace(" ", "-").replace("/", "-")
    return f"Korean::Lessons::{transcription.lesson_id}::{normalized}"


def _to_item(
    transcription: LessonTranscription,
    section_id: str,
    item_type: ItemType,
    section_usage_notes: list[str],
    section_tags: list[str],
    entry: TranscriptionEntry,
    index: int,
) -> LessonItem:
    examples: list[ExampleSentence] = []
    notes = entry.notes
    if notes is None and section_usage_notes:
        notes = " ".join(section_usage_notes)

    return LessonItem(
        id=f"{transcription.lesson_id}-{section_id}-{index:03d}",
        lesson_id=f"{transcription.lesson_id}-{section_id}",
        item_type=item_type,
        korean=entry.korean,
        english=entry.english,
        pronunciation=entry.pronunciation,
        examples=examples,
        notes=notes,
        tags=section_tags,
        source_ref=f"{entry.label} • {section_id}",
        audio=None,
        image=None,
    )


def build_lesson_documents(transcription: LessonTranscription) -> list[LessonDocument]:
    documents: list[LessonDocument] = []
    for section in transcription.sections:
        metadata = LessonMetadata(
            lesson_id=f"{transcription.lesson_id}-{section.id}",
            title=f"{transcription.title} - {section.title}",
            topic=section.title,
            lesson_date=transcription.lesson_date,
            source_description=transcription.source_summary,
            target_deck=section.target_deck or _default_deck(transcription, section.title),
            tags=section.tags,
        )
        documents.append(
            LessonDocument(
                metadata=metadata,
                items=[
                    _to_item(transcription, section.id, section.item_type, section.usage_notes, section.tags, entry, index)
                    for index, entry in enumerate(section.entries, start=1)
                ],
            )
        )
    return documents


def qa_transcription(transcription: LessonTranscription) -> QaReport:
    issues: list[QaIssue] = []

    if transcription.expected_section_count is not None and len(transcription.sections) != transcription.expected_section_count:
        issues.append(
            QaIssue(
                severity="error",
                code="section_count_mismatch",
                message=(
                    f"Expected {transcription.expected_section_count} section(s), "
                    f"found {len(transcription.sections)}."
                ),
            )
        )

    section_ids = [section.id for section in transcription.sections]
    duplicate_section_ids = [section_id for section_id, count in Counter(section_ids).items() if count > 1]
    for section_id in duplicate_section_ids:
        issues.append(
            QaIssue(
                severity="error",
                code="duplicate_section_id",
                message=f"Duplicate section id: {section_id}.",
                section_id=section_id,
            )
        )

    for section in transcription.sections:
        if section.expected_entry_count is not None and len(section.entries) != section.expected_entry_count:
            issues.append(
                QaIssue(
                    severity="error",
                    code="entry_count_mismatch",
                    message=(
                        f"Section {section.id} expected {section.expected_entry_count} entries, "
                        f"found {len(section.entries)}."
                    ),
                    section_id=section.id,
                )
            )

        if not section.usage_notes:
            issues.append(
                QaIssue(
                    severity="warning",
                    code="missing_usage_notes",
                    message=f"Section {section.id} has no usage notes.",
                    section_id=section.id,
                )
            )

        labels = [entry.label for entry in section.entries]
        duplicate_labels = [label for label, count in Counter(labels).items() if count > 1]
        for label in duplicate_labels:
            issues.append(
                QaIssue(
                    severity="error",
                    code="duplicate_entry_label",
                    message=f"Duplicate entry label in section {section.id}: {label}.",
                    section_id=section.id,
                )
            )

    if not transcription.theme.strip():
        issues.append(
            QaIssue(
                severity="error",
                code="missing_theme",
                message="Transcription theme is empty.",
            )
        )

    if not transcription.goals:
        issues.append(
            QaIssue(
                severity="warning",
                code="missing_goals",
                message="No lesson goals were recorded.",
            )
        )

    return QaReport(
        lesson_id=transcription.lesson_id,
        passed=not any(issue.severity == "error" for issue in issues),
        issues=issues,
    )


def write_lesson_documents(documents: list[LessonDocument], output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []
    for document in documents:
        output_path = output_dir / f"{document.metadata.lesson_id}.lesson.json"
        output_path.write_text(document.model_dump_json(indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        written.append(output_path)
    return written
