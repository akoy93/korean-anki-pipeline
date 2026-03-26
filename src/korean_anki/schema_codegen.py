from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

from pydantic import TypeAdapter

from . import schema as backend_schema

PREVIEW_CONTRACT_LITERAL_EXPORTS = (
    "BatchPushStatus",
    "JobKind",
    "JobStatus",
    "StudyLane",
)

PREVIEW_CONTRACT_MODEL_EXPORTS = (
    "CardBatch",
    "CardPreview",
    "DashboardBatch",
    "DashboardResponse",
    "DeleteBatchResult",
    "GeneratedNote",
    "JobResponse",
    "LessonItem",
    "PushResult",
)


def _strip_nested_schema_titles(value: Any) -> Any:
    if isinstance(value, dict):
        result: dict[str, Any] = {}
        for key, item in value.items():
            if key == "title":
                continue
            if key in {"properties", "$defs"} and isinstance(item, dict):
                result[key] = {
                    name: _strip_nested_schema_titles(schema)
                    for name, schema in item.items()
                }
                continue
            result[key] = _strip_nested_schema_titles(item)
        return result

    if isinstance(value, list):
        return [_strip_nested_schema_titles(item) for item in value]

    return value


def _backend_schema_value(name: str) -> Any:
    try:
        return getattr(backend_schema, name)
    except AttributeError as error:
        raise RuntimeError(f"Backend schema export {name!r} was not found.") from error


def _flatten_definition_schema(schema: dict[str, Any], contract_defs: dict[str, Any]) -> dict[str, Any]:
    flattened = _strip_nested_schema_titles(schema)
    nested_defs = flattened.pop("$defs", None)
    if isinstance(nested_defs, dict):
        for definition_name in sorted(nested_defs):
            _store_contract_definition(contract_defs, definition_name, nested_defs[definition_name])
    return flattened


def _store_contract_definition(
    contract_defs: dict[str, Any],
    definition_name: str,
    schema: dict[str, Any],
) -> None:
    flattened = _flatten_definition_schema(schema, contract_defs)
    flattened["title"] = definition_name
    existing = contract_defs.get(definition_name)
    if existing is None:
        contract_defs[definition_name] = flattened
        return
    if existing != flattened:
        raise RuntimeError(
            f"Preview contract definition {definition_name!r} was generated inconsistently."
        )


def build_preview_contract_schema() -> dict[str, Any]:
    contract_defs: dict[str, Any] = {}
    contract: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "PreviewContract",
        "type": "object",
    }

    for alias_name in PREVIEW_CONTRACT_LITERAL_EXPORTS:
        alias_schema = TypeAdapter(_backend_schema_value(alias_name)).json_schema(
            ref_template="#/$defs/{model}"
        )
        _store_contract_definition(contract_defs, alias_name, alias_schema)

    for model_name in PREVIEW_CONTRACT_MODEL_EXPORTS:
        model = _backend_schema_value(model_name)
        model_schema = model.model_json_schema(ref_template="#/$defs/{model}")
        _store_contract_definition(contract_defs, model_name, model_schema)

    contract["$defs"] = {name: contract_defs[name] for name in sorted(contract_defs)}
    return contract


def render_preview_contract_schema_json() -> str:
    return json.dumps(
        build_preview_contract_schema(),
        ensure_ascii=False,
        indent=2,
    ) + "\n"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Generate the preview JSON Schema contract from the backend schema."
    )
    parser.add_argument("--write", type=Path, help="Write the generated JSON Schema to this path.")
    parser.add_argument(
        "--check",
        type=Path,
        help="Fail if the generated JSON Schema does not match the existing file.",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    rendered = render_preview_contract_schema_json()

    if args.check is not None:
        existing = args.check.read_text(encoding="utf-8")
        if existing != rendered:
            print(f"{args.check} is out of date. Regenerate it with --write.")
            return 1
        return 0

    if args.write is not None:
        args.write.write_text(rendered, encoding="utf-8")
        return 0

    print(rendered, end="")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
