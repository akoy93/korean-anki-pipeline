from __future__ import annotations


def lesson_json_schema() -> dict[str, object]:
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


def transcription_json_schema() -> dict[str, object]:
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


def pronunciation_json_schema() -> dict[str, object]:
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


def image_decision_json_schema() -> dict[str, object]:
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


def new_vocab_proposal_json_schema() -> dict[str, object]:
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
