from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from .lesson_io import read_lesson, read_transcription, write_json
from .llm_prompts import (
    IMAGE_DECISION_SYSTEM_PROMPT,
    NEW_VOCAB_SYSTEM_PROMPT,
    PRONUNCIATION_SYSTEM_PROMPT,
    SYSTEM_PROMPT,
    TRANSCRIPTION_SYSTEM_PROMPT,
)
from .openai_client import create_openai_client
from .schema import (
    ExtractionRequest,
    ImageGenerationPlan,
    LessonExtractionDocument,
    LessonDocument,
    LessonTranscription,
    LessonTranscriptionOutput,
    NewVocabProposalBatch,
    PronunciationBatch,
    RawSourceAsset,
)
from .settings import DEFAULT_LLM_MODEL
from .structured_outputs import response_json_schema


def _build_user_text(request: ExtractionRequest) -> str:
    parts = [
        f"lesson_id: {request.lesson_id}",
        f"title: {request.title}",
        f"topic: {request.topic}",
        f"lesson_date: {request.lesson_date.isoformat()}",
        f"source_description: {request.source_description}",
        f"default_item_type: {request.item_type_default}",
    ]
    if request.text is not None:
        parts.append("source_text:")
        parts.append(request.text)
    return "\n".join(parts)


def _image_data_url(image_path: Path) -> str:
    image_bytes = image_path.read_bytes()
    mime_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
    return f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"


def extract_lesson(request: ExtractionRequest) -> LessonDocument:
    client = create_openai_client()
    content: list[dict[str, object]] = [{"type": "input_text", "text": _build_user_text(request)}]
    if request.image_path is not None:
        content.append({"type": "input_image", "image_url": _image_data_url(Path(request.image_path))})
    lesson_format = {"type": "json_schema", **response_json_schema("lesson_document", LessonExtractionDocument)}

    response = client.responses.create(
        model=request.model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        text={"format": lesson_format},
        reasoning={"effort": "medium"},
    )
    extracted_document = LessonExtractionDocument.model_validate_json(response.output_text)
    document = LessonDocument.model_validate(extracted_document.model_dump())

    if not request.run_qa:
        return document

    qa_response = client.responses.create(
        model=request.qa_model,
        input=[
            {
                "role": "system",
                "content": (
                    "You are a QA pass for Korean study material. Return corrected JSON only. "
                    "Preserve schema. Fix obvious extraction mistakes, malformed examples, "
                    "and bad item_type classifications. Do not add speculative content."
                ),
            },
            {"role": "user", "content": document.model_dump_json(indent=2)},
        ],
        text={"format": lesson_format},
        reasoning={"effort": "high"},
    )
    qa_document = LessonExtractionDocument.model_validate_json(qa_response.output_text)
    return LessonDocument.model_validate(qa_document.model_dump())


def transcribe_sources(
    *,
    lesson_id: str,
    title: str,
    lesson_date: str,
    source_summary: str,
    raw_sources: list[RawSourceAsset],
    model: str = DEFAULT_LLM_MODEL,
) -> LessonTranscription:
    client = create_openai_client()
    transcription_format = {
        "type": "json_schema",
        **response_json_schema("lesson_transcription", LessonTranscriptionOutput),
    }
    content: list[dict[str, object]] = [
        {
            "type": "input_text",
            "text": "\n".join(
                [
                    f"lesson_id: {lesson_id}",
                    f"title: {title}",
                    f"lesson_date: {lesson_date}",
                    f"source_summary: {source_summary}",
                    "Transcribe the attached source material into structured sections.",
                ]
            ),
        }
    ]

    for source in raw_sources:
        if source.kind == "text":
            content.append(
                {
                    "type": "input_text",
                    "text": f"Raw text source ({source.path}):\n{Path(source.path).read_text(encoding='utf-8')}",
                }
            )
            continue
        content.append({"type": "input_image", "image_url": _image_data_url(Path(source.path))})

    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": TRANSCRIPTION_SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        text={"format": transcription_format},
        reasoning={"effort": "high"},
    )
    transcription_output = LessonTranscriptionOutput.model_validate_json(response.output_text)
    transcription = LessonTranscription.model_validate(transcription_output.model_dump())
    return transcription.model_copy(update={"raw_sources": raw_sources})


def generate_pronunciations(
    korean_texts: list[str],
    model: str = DEFAULT_LLM_MODEL,
) -> dict[str, str]:
    unique_texts = list(dict.fromkeys(text for text in korean_texts if text.strip()))
    if not unique_texts:
        return {}

    client = create_openai_client()
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": PRONUNCIATION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "\n".join(
                    [
                        "Generate one romanization for each Korean string.",
                        "Inputs:",
                        *unique_texts,
                    ]
                ),
            },
        ],
        text={"format": {"type": "json_schema", **response_json_schema("pronunciation_batch", PronunciationBatch)}},
        reasoning={"effort": "low"},
    )
    batch = PronunciationBatch.model_validate_json(response.output_text)
    return {item.korean: item.pronunciation for item in batch.items}


def plan_image_generation(
    document: LessonDocument,
    model: str = DEFAULT_LLM_MODEL,
) -> dict[str, bool]:
    candidates = [
        item
        for item in document.items
        if item.image is None and item.item_type in {"vocab", "phrase", "dialogue"}
    ]
    if not candidates:
        return {}

    client = create_openai_client()
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": IMAGE_DECISION_SYSTEM_PROMPT},
            {
                "role": "user",
                "content": "\n".join(
                    [
                        f"Lesson title: {document.metadata.title}",
                        f"Lesson topic: {document.metadata.topic}",
                        "Candidate items:",
                        *[
                            (
                                f"- item_id: {item.id} | item_type: {item.item_type} | "
                                f"korean: {item.korean} | english: {item.english} | notes: {item.notes or ''}"
                            )
                            for item in candidates
                        ],
                    ]
                ),
            },
        ],
        text={"format": {"type": "json_schema", **response_json_schema("image_generation_plan", ImageGenerationPlan)}},
        reasoning={"effort": "low"},
    )

    plan = ImageGenerationPlan.model_validate_json(response.output_text)
    decisions = {decision.item_id: decision.generate_image for decision in plan.decisions}
    missing_item_ids = [item.id for item in candidates if item.id not in decisions]
    if missing_item_ids:
        raise RuntimeError(f"Image decision model omitted item ids: {', '.join(missing_item_ids)}")

    return decisions


def propose_new_vocab(
    *,
    model: str = DEFAULT_LLM_MODEL,
    candidate_count: int,
    batch_theme: str,
    target_gap_topics: list[str],
    lesson_context_summary: str | None,
    lesson_context_tags: list[str],
    excluded_pairs: list[str],
) -> NewVocabProposalBatch:
    client = create_openai_client()
    lines = [
        f"Propose {candidate_count} candidate vocab items.",
        f"Batch theme: {batch_theme}",
        "All candidates must fit this single cohesive theme.",
        f"Target coverage-gap topics: {', '.join(target_gap_topics)}",
        (
            f"Latest lesson context: {lesson_context_summary}"
            if lesson_context_summary is not None
            else "No latest lesson context provided; use coverage-gap proposals only."
        ),
        f"Latest lesson tags: {', '.join(lesson_context_tags) if lesson_context_tags else '(none)'}",
        "Excluded known words (normalized korean | english):",
        *(excluded_pairs[:200] or ["(none)"]),
        "Return a diverse pool. If lesson context is present, include both coverage-gap and lesson-adjacent candidates.",
    ]
    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": NEW_VOCAB_SYSTEM_PROMPT},
            {"role": "user", "content": "\n".join(lines)},
        ],
        text={"format": {"type": "json_schema", **response_json_schema("new_vocab_proposal_batch", NewVocabProposalBatch)}},
        reasoning={"effort": "medium"},
    )
    return NewVocabProposalBatch.model_validate_json(response.output_text)


__all__ = [
    "extract_lesson",
    "generate_pronunciations",
    "plan_image_generation",
    "propose_new_vocab",
    "read_lesson",
    "read_transcription",
    "transcribe_sources",
    "write_json",
]
