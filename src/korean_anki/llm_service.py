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
    selection_strategy: str,
    known_vocab_count: int,
    batch_theme: str | None,
    target_gap_topics: list[str],
    curriculum_focus_topics: list[str],
    topic_coverage_counts: dict[str, int],
    lesson_context_summary: str | None,
    lesson_context_tags: list[str],
    excluded_pairs: list[str],
) -> NewVocabProposalBatch:
    client = create_openai_client()
    lines = [
        f"Propose {candidate_count} candidate vocab items.",
        f"Learner known vocabulary count estimate: {known_vocab_count}",
        "Assume the learner is A1 and still building their first core everyday vocabulary.",
        "Return part_of_speech for each proposal: noun, verb, adjective, or fixed-expression.",
        "Return target_form='headword' for nouns and dictionary-form verbs/adjectives.",
        "Return utility_band for each proposal: core, supporting, or expansion.",
        "Return frequency_band for each proposal: high, medium, or low.",
        "Return usage_register for each proposal: everyday-spoken, polite-formula, formal-written, literary, or niche.",
        "Use target_form='fixed-expression' only for expressions that a beginner should memorize as one chunk.",
        f"Target coverage-gap topics: {', '.join(target_gap_topics)}",
        (
            f"Current curriculum focus topics: {', '.join(curriculum_focus_topics)}"
            if curriculum_focus_topics
            else "Current curriculum focus topics: (none)"
        ),
        "Current unique known/generated vocabulary counts by topic:",
        *[
            f"- {topic}: {topic_coverage_counts.get(topic, 0)}"
            for topic in sorted(topic_coverage_counts)
        ],
        (
            f"Latest lesson context: {lesson_context_summary}"
            if lesson_context_summary is not None
            else "No latest lesson context provided; use coverage-gap proposals only."
        ),
        f"Latest lesson tags: {', '.join(lesson_context_tags) if lesson_context_tags else '(none)'}",
        "Bias heavily toward the next most useful beginner words before broader or more specialized words.",
        "Prefer survival vocabulary, polite formulas, routine nouns, places, time words, food, greetings, and simple dictionary-form actions over descriptive or niche vocabulary.",
        "Excluded known words (normalized korean | english):",
        *(excluded_pairs[:200] or ["(none)"]),
    ]
    if selection_strategy == "themed":
        lines.extend(
            [
                f"Batch theme: {batch_theme or '(none)'}",
                "All candidates must fit this single cohesive theme.",
                "Keep the theme coherent, but still choose the highest-utility beginner words inside it first.",
            ]
        )
    elif selection_strategy == "hybrid":
        lines.extend(
            [
                "Do not force a single narrow theme.",
                "Prefer globally useful beginner vocabulary first, but it is acceptable if the batch clusters loosely around one or two current focus topics.",
                "If lesson context is present, you may include some lesson-adjacent vocabulary, but do not sacrifice beginner utility for topical purity.",
            ]
        )
    else:
        lines.extend(
            [
                "Do not force a single narrow theme.",
                "This is an early-stage utility-first batch. Choose the next words a true beginner should know soonest, even if they span multiple topics.",
                "Especially value greetings, thanks, apologies, polite set phrases, numbers, time words, basic places, and simple everyday actions.",
                "Favor high-frequency everyday-spoken words and polite formulas. Avoid low-frequency, formal-written, literary, or niche vocabulary.",
                "Aim for breadth across the current focus topics rather than thematic purity.",
            ]
        )
    lines.append(
        "Return a diverse pool. If lesson context is present, include lesson-adjacent candidates only when they are still genuinely high-utility for a beginner."
    )
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
