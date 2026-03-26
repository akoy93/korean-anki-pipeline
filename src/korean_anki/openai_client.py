from __future__ import annotations

from openai import OpenAI


def create_openai_client() -> OpenAI:
    return OpenAI()
