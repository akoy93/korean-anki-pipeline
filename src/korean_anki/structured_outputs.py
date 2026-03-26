from __future__ import annotations

from typing import Any

from pydantic import BaseModel


def _strip_schema_metadata(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: _strip_schema_metadata(item)
            for key, item in value.items()
            if key not in {"title", "default"}
        }
    if isinstance(value, list):
        return [_strip_schema_metadata(item) for item in value]
    return value


def response_json_schema(name: str, model: type[BaseModel]) -> dict[str, object]:
    return {
        "name": name,
        "schema": _strip_schema_metadata(model.model_json_schema(ref_template="#/$defs/{model}")),
        "strict": True,
    }
