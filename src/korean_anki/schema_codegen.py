from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any, Literal, get_origin

from pydantic import TypeAdapter

from . import schema as backend_schema
from .schema import StrictModel


def _literal_alias_names() -> list[str]:
    names: list[str] = []
    for name, value in vars(backend_schema).items():
        if name.startswith("_"):
            continue
        if get_origin(value) is Literal:
            names.append(name)
    return names


def _model_names() -> list[str]:
    names: list[str] = []
    for name, value in vars(backend_schema).items():
        if name == "StrictModel":
            continue
        if isinstance(value, type) and issubclass(value, StrictModel):
            names.append(name)
    return names


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


def build_preview_contract_schema() -> dict[str, Any]:
    contract: dict[str, Any] = {
        "$schema": "https://json-schema.org/draft/2020-12/schema",
        "title": "PreviewContract",
        "type": "object",
        "$defs": {},
    }

    for alias_name in _literal_alias_names():
        alias_schema = TypeAdapter(getattr(backend_schema, alias_name)).json_schema(
            ref_template="#/$defs/{model}"
        )
        alias_schema = _strip_nested_schema_titles(alias_schema)
        alias_schema["title"] = alias_name
        contract["$defs"][alias_name] = alias_schema

    for model_name in _model_names():
        model = getattr(backend_schema, model_name)
        model_schema = model.model_json_schema(ref_template="#/$defs/{model}")
        model_schema = _strip_nested_schema_titles(model_schema)
        model_schema["title"] = model_name
        contract["$defs"][model_name] = model_schema

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
