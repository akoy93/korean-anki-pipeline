from __future__ import annotations

import base64
import mimetypes
from pathlib import Path

from openai import OpenAI

from .schema import (
    ExtractionRequest,
    ImageGenerationPlan,
    LessonDocument,
    LessonTranscription,
    NewVocabProposalBatch,
    PronunciationBatch,
    RawSourceAsset,
)


SYSTEM_PROMPT = """You extract Korean study material into a strict JSON lesson document.

Rules:
- Return only valid JSON matching the requested schema.
- Keep one atomic concept per item.
- Required fields must be present directly.
- Use item_type only from: vocab, phrase, grammar, dialogue, number.
- Prefer concise example sentences when source material supports them.
- If pronunciation is included, use a learner-friendly romanization.
"""

TRANSCRIPTION_SYSTEM_PROMPT = """You are doing faithful source transcription for Korean lesson material.

Return a structured transcription that preserves source layout and section boundaries.
Rules:
- Capture every visible section separately. Do not merge number systems or columns.
- Preserve side/position labels when visible (for example left side, right side).
- Transcribe all visible entries and larger-unit rows, not just the first list.
- Extract usage notes from the source separately for each section.
- Summarize the overall lesson theme and study goals.
- Do not invent entries that are not visible in the source.
- If a section has an obvious expected count, include it.
"""

PRONUNCIATION_SYSTEM_PROMPT = """You generate learner-friendly romanization for Korean study cards.

Rules:
- Return only valid JSON matching the requested schema.
- Preserve the input order exactly.
- Keep each pronunciation concise and readable for an English-speaking learner.
- Do not add extra explanation, punctuation, or IPA.
"""

IMAGE_DECISION_SYSTEM_PROMPT = """You decide whether a Korean flashcard should get an AI-generated image.

Rules:
- Return only valid JSON matching the requested schema.
- Return one decision for every candidate item, preserving input order exactly.
- Choose generate_image=true only when a simple concrete image or scene would likely improve recall.
- Choose generate_image=false for abstract meanings, function words, grammar, numbers, or items where usage context matters more than visual identity.
- Keep reasons short and specific.
"""

NEW_VOCAB_SYSTEM_PROMPT = """You propose beginner Korean vocabulary for a TOPIK I learner.

Rules:
- Return only valid JSON matching the requested schema.
- Propose A1-level, high-utility words only.
- Keep one atomic meaning per item.
- Prefer everyday words a beginner can use immediately.
- Do not repeat excluded words or near-repeats if avoidable.
- For every item, provide a simple example sentence and an image prompt.
- The image prompt must describe a polished, engaging illustration for an adult learner, with no text in the image.
- If the image prompt includes people, depict Korean people in a natural contemporary Korean setting.
- Use adjacency_kind='coverage-gap' for topic gap fill and 'lesson-adjacent' for words that naturally co-occur with the lesson context.
"""


def _lesson_json_schema() -> dict[str, object]:
    return {
        "name": "lesson_document",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["schema_version", "metadata", "items"],
            "properties": {
                "schema_version": {"type": "string", "const": "1"},
                "metadata": {
                    "type": "object",
                    "additionalProperties": False,
                    "required": [
                        "lesson_id",
                        "title",
                        "topic",
                        "lesson_date",
                        "source_description",
                        "target_deck",
                        "tags",
                    ],
                    "properties": {
                        "lesson_id": {"type": "string"},
                        "title": {"type": "string"},
                        "topic": {"type": "string"},
                        "lesson_date": {"type": "string", "format": "date"},
                        "source_description": {"type": "string"},
                        "target_deck": {"type": ["string", "null"]},
                        "tags": {"type": "array", "items": {"type": "string"}},
                    },
                },
                "items": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "id",
                            "lesson_id",
                            "item_type",
                            "korean",
                            "english",
                            "pronunciation",
                            "examples",
                            "notes",
                            "tags",
                            "source_ref",
                            "audio",
                            "image",
                        ],
                        "properties": {
                            "id": {"type": "string"},
                            "lesson_id": {"type": "string"},
                            "item_type": {
                                "type": "string",
                                "enum": ["vocab", "phrase", "grammar", "dialogue", "number"],
                            },
                            "korean": {"type": "string"},
                            "english": {"type": "string"},
                            "pronunciation": {"type": ["string", "null"]},
                            "examples": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "additionalProperties": False,
                                    "required": ["korean", "english"],
                                    "properties": {
                                        "korean": {"type": "string"},
                                        "english": {"type": "string"},
                                    },
                                },
                            },
                            "notes": {"type": ["string", "null"]},
                            "tags": {"type": "array", "items": {"type": "string"}},
                            "source_ref": {"type": ["string", "null"]},
                            "audio": {"type": "null"},
                            "image": {"type": "null"},
                        },
                    },
                },
            },
        },
        "strict": True,
    }


def _transcription_json_schema() -> dict[str, object]:
    entry = {
        "type": "object",
        "additionalProperties": False,
        "required": ["label", "korean", "english", "pronunciation", "notes"],
        "properties": {
            "label": {"type": "string"},
            "korean": {"type": "string"},
            "english": {"type": "string"},
            "pronunciation": {"type": ["string", "null"]},
            "notes": {"type": ["string", "null"]},
        },
    }
    section = {
        "type": "object",
        "additionalProperties": False,
        "required": [
            "id",
            "title",
            "item_type",
            "side",
            "number_system",
            "usage_notes",
            "expected_entry_count",
            "target_deck",
            "tags",
            "entries",
        ],
        "properties": {
            "id": {"type": "string"},
            "title": {"type": "string"},
            "item_type": {
                "type": "string",
                "enum": ["vocab", "phrase", "grammar", "dialogue", "number"],
            },
            "side": {"type": ["string", "null"]},
            "number_system": {"type": ["string", "null"]},
            "usage_notes": {"type": "array", "items": {"type": "string"}},
            "expected_entry_count": {"type": ["integer", "null"]},
            "target_deck": {"type": ["string", "null"]},
            "tags": {"type": "array", "items": {"type": "string"}},
            "entries": {"type": "array", "minItems": 1, "items": entry},
        },
    }
    return {
        "name": "lesson_transcription",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": [
                "schema_version",
                "lesson_id",
                "title",
                "lesson_date",
                "source_summary",
                "theme",
                "goals",
                "raw_sources",
                "expected_section_count",
                "sections",
                "notes",
            ],
            "properties": {
                "schema_version": {"type": "string", "const": "1"},
                "lesson_id": {"type": "string"},
                "title": {"type": "string"},
                "lesson_date": {"type": "string", "format": "date"},
                "source_summary": {"type": "string"},
                "theme": {"type": "string"},
                "goals": {"type": "array", "items": {"type": "string"}},
                "raw_sources": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["kind", "path", "description"],
                        "properties": {
                            "kind": {"type": "string", "enum": ["image", "text"]},
                            "path": {"type": "string"},
                            "description": {"type": "string"},
                        },
                    },
                },
                "expected_section_count": {"type": ["integer", "null"]},
                "sections": {"type": "array", "minItems": 1, "items": section},
                "notes": {"type": "array", "items": {"type": "string"}},
            },
        },
        "strict": True,
    }


def _pronunciation_json_schema() -> dict[str, object]:
    return {
        "name": "pronunciation_batch",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["items"],
            "properties": {
                "items": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["korean", "pronunciation"],
                        "properties": {
                            "korean": {"type": "string"},
                            "pronunciation": {"type": "string"},
                        },
                    },
                }
            },
        },
        "strict": True,
    }


def _image_decision_json_schema() -> dict[str, object]:
    return {
        "name": "image_generation_plan",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["decisions"],
            "properties": {
                "decisions": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": ["item_id", "generate_image", "reason"],
                        "properties": {
                            "item_id": {"type": "string"},
                            "generate_image": {"type": "boolean"},
                            "reason": {"type": "string"},
                        },
                    },
                }
            },
        },
        "strict": True,
    }


def _new_vocab_proposal_json_schema() -> dict[str, object]:
    return {
        "name": "new_vocab_proposal_batch",
        "schema": {
            "type": "object",
            "additionalProperties": False,
            "required": ["proposals"],
            "properties": {
                "proposals": {
                    "type": "array",
                    "minItems": 1,
                    "items": {
                        "type": "object",
                        "additionalProperties": False,
                        "required": [
                            "candidate_id",
                            "korean",
                            "english",
                            "topic_tag",
                            "example_ko",
                            "example_en",
                            "proposal_reason",
                            "image_prompt",
                            "adjacency_kind",
                        ],
                        "properties": {
                            "candidate_id": {"type": "string"},
                            "korean": {"type": "string"},
                            "english": {"type": "string"},
                            "topic_tag": {"type": "string"},
                            "example_ko": {"type": "string"},
                            "example_en": {"type": "string"},
                            "proposal_reason": {"type": "string"},
                            "image_prompt": {"type": "string"},
                            "adjacency_kind": {
                                "type": "string",
                                "enum": ["coverage-gap", "lesson-adjacent"],
                            },
                        },
                    },
                },
            },
        },
        "strict": True,
    }


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


def extract_lesson(request: ExtractionRequest) -> LessonDocument:
    client = OpenAI()
    content: list[dict[str, object]] = [{"type": "input_text", "text": _build_user_text(request)}]
    if request.image_path is not None:
        image_path = Path(request.image_path)
        image_bytes = image_path.read_bytes()
        mime_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
        data_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
        content.append(
            {
                "type": "input_image",
                "image_url": data_url,
            }
        )

    response = client.responses.create(
        model=request.model,
        input=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        text={
            "format": {
                "type": "json_schema",
                **_lesson_json_schema(),
            }
        },
        reasoning={"effort": "medium"},
    )
    document = LessonDocument.model_validate_json(response.output_text)

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
        text={
            "format": {
                "type": "json_schema",
                **_lesson_json_schema(),
            }
        },
        reasoning={"effort": "high"},
    )
    return LessonDocument.model_validate_json(qa_response.output_text)


def transcribe_sources(
    *,
    lesson_id: str,
    title: str,
    lesson_date: str,
    source_summary: str,
    raw_sources: list[RawSourceAsset],
    model: str = "gpt-5.4",
) -> LessonTranscription:
    client = OpenAI()
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

        image_path = Path(source.path)
        image_bytes = image_path.read_bytes()
        mime_type = mimetypes.guess_type(image_path.name)[0] or "image/png"
        data_url = f"data:{mime_type};base64,{base64.b64encode(image_bytes).decode('ascii')}"
        content.append({"type": "input_image", "image_url": data_url})

    response = client.responses.create(
        model=model,
        input=[
            {"role": "system", "content": TRANSCRIPTION_SYSTEM_PROMPT},
            {"role": "user", "content": content},
        ],
        text={
            "format": {
                "type": "json_schema",
                **_transcription_json_schema(),
            }
        },
        reasoning={"effort": "high"},
    )
    transcription = LessonTranscription.model_validate_json(response.output_text)
    return transcription.model_copy(update={"raw_sources": raw_sources})


def generate_pronunciations(
    korean_texts: list[str],
    model: str = "gpt-5.4",
) -> dict[str, str]:
    unique_texts = list(dict.fromkeys(text for text in korean_texts if text.strip()))
    if not unique_texts:
        return {}

    client = OpenAI()
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
        text={
            "format": {
                "type": "json_schema",
                **_pronunciation_json_schema(),
            }
        },
        reasoning={"effort": "low"},
    )
    batch = PronunciationBatch.model_validate_json(response.output_text)
    return {item.korean: item.pronunciation for item in batch.items}


def plan_image_generation(
    document: LessonDocument,
    model: str = "gpt-5.4",
) -> dict[str, bool]:
    candidates = [
        item
        for item in document.items
        if item.image is None and item.item_type in {"vocab", "phrase", "dialogue"}
    ]
    if not candidates:
        return {}

    client = OpenAI()
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
        text={
            "format": {
                "type": "json_schema",
                **_image_decision_json_schema(),
            }
        },
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
    model: str = "gpt-5.4",
    candidate_count: int,
    target_gap_topics: list[str],
    lesson_context_summary: str | None,
    lesson_context_tags: list[str],
    excluded_pairs: list[str],
) -> NewVocabProposalBatch:
    client = OpenAI()
    lines = [
        f"Propose {candidate_count} candidate vocab items.",
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
        text={
            "format": {
                "type": "json_schema",
                **_new_vocab_proposal_json_schema(),
            }
        },
        reasoning={"effort": "high"},
    )
    return NewVocabProposalBatch.model_validate_json(response.output_text)


def write_json(document: LessonDocument, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(document.model_dump_json(indent=2, ensure_ascii=False) + "\n", encoding="utf-8")


def read_lesson(path: Path) -> LessonDocument:
    return LessonDocument.model_validate_json(path.read_text(encoding="utf-8"))


def read_transcription(path: Path) -> LessonTranscription:
    return LessonTranscription.model_validate_json(path.read_text(encoding="utf-8"))
