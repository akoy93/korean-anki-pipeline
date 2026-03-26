from __future__ import annotations

from dataclasses import dataclass
from email.parser import BytesParser
from email.policy import default
from io import BytesIO
from pathlib import Path


@dataclass
class MultipartField:
    name: str
    value: str | None = None
    filename: str | None = None
    file: BytesIO | None = None


class MultipartForm:
    def __init__(self, fields: dict[str, list[MultipartField]]) -> None:
        self._fields = fields

    def __contains__(self, key: str) -> bool:
        return key in self._fields

    def __getitem__(self, key: str) -> MultipartField | list[MultipartField]:
        values = self._fields[key]
        if len(values) == 1:
            return values[0]
        return values

    def getvalue(self, key: str) -> str | list[str] | None:
        values = self._fields.get(key)
        if not values:
            return None
        text_values = [value.value for value in values if value.value is not None]
        if not text_values:
            return None
        if len(text_values) == 1:
            return text_values[0]
        return text_values

    @classmethod
    def parse(cls, content_type: str, raw_body: bytes) -> MultipartForm:
        parser = BytesParser(policy=default)
        message = parser.parsebytes(
            (
                f"Content-Type: {content_type}\r\n"
                "MIME-Version: 1.0\r\n"
                "\r\n"
            ).encode("utf-8")
            + raw_body
        )
        if not message.is_multipart():
            raise ValueError("Expected multipart form-data request.")

        fields: dict[str, list[MultipartField]] = {}
        for part in message.iter_parts():
            if part.get_content_disposition() != "form-data":
                continue

            name = part.get_param("name", header="content-disposition")
            if not isinstance(name, str) or not name:
                continue

            payload = part.get_payload(decode=True) or b""
            filename = part.get_filename()
            value = None
            file = None
            if filename is None:
                charset = part.get_content_charset() or "utf-8"
                value = payload.decode(charset)
            else:
                file = BytesIO(payload)

            fields.setdefault(name, []).append(
                MultipartField(name=name, value=value, filename=filename, file=file)
            )

        return cls(fields)


def parse_bool_field(value: str | None, default: bool = False) -> bool:
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def field_value(form: MultipartForm, key: str) -> str | None:
    if key not in form:
        return None
    value = form.getvalue(key)
    if isinstance(value, str):
        return value
    return None


def save_upload(file_item: MultipartField, output_path: Path) -> None:
    if file_item.file is None:
        raise ValueError("Uploaded field is missing file content.")
    file_item.file.seek(0)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("wb") as handle:
        handle.write(file_item.file.read())
