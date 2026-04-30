"""Thin Claude wrapper used by all LLM agents.

Centralizes: model selection, retry on transient errors, JSON extraction,
Pydantic validation, and Langfuse generation logging.
"""

from __future__ import annotations

import json
import os
import re
import time
from typing import TypeVar

from anthropic import Anthropic, APIError
from pydantic import BaseModel, ValidationError

from src.tracing import llm_generation

T = TypeVar("T", bound=BaseModel)

_DEFAULT_MODEL = os.getenv("ANTHROPIC_MODEL", "claude-haiku-4-5-20251001")

_client: Anthropic | None = None


def _get_client() -> Anthropic:
    global _client
    if _client is None:
        _client = Anthropic()
    return _client


_JSON_BLOCK = re.compile(r"```(?:json)?\s*(\{.*?\}|\[.*?\])\s*```", re.DOTALL)


def _extract_json(text: str) -> str:
    """Pull a JSON object/array out of a Claude response.

    Claude is good at honoring 'respond with JSON only', but occasionally wraps
    output in a code fence or adds a sentence. We handle both.
    """
    m = _JSON_BLOCK.search(text)
    if m:
        return m.group(1)
    start = next((i for i, c in enumerate(text) if c in "{["), None)
    if start is None:
        raise ValueError(f"No JSON found in response: {text[:200]!r}")
    end = max(text.rfind("}"), text.rfind("]"))
    if end < start:
        raise ValueError(f"Truncated JSON in response: {text[:200]!r}")
    return text[start : end + 1]


def call_structured(
    *,
    system: str,
    user: str,
    response_model: type[T],
    model: str | None = None,
    max_tokens: int = 2048,
    temperature: float = 0.4,
    max_retries: int = 2,
    span_name: str = "claude_call",
) -> T:
    """Call Claude and validate response against a Pydantic model.

    Wraps the call in a Langfuse generation span (no-op if Langfuse disabled).
    """
    chosen_model = model or _DEFAULT_MODEL
    client = _get_client()

    with llm_generation(
        span_name,
        model=chosen_model,
        input_payload={"system": system, "user": user},
    ) as gen:
        last_err: Exception | None = None
        raw_text = ""
        for attempt in range(max_retries + 1):
            try:
                resp = client.messages.create(
                    model=chosen_model,
                    max_tokens=max_tokens,
                    temperature=temperature,
                    system=system,
                    messages=[{"role": "user", "content": user}],
                )
                raw_text = "".join(b.text for b in resp.content if b.type == "text")
                parsed = json.loads(_extract_json(raw_text))
                validated = response_model.model_validate(parsed)
                gen.update(
                    output=validated.model_dump(),
                    usage_details={
                        "input": resp.usage.input_tokens,
                        "output": resp.usage.output_tokens,
                    },
                )
                return validated
            except (APIError, json.JSONDecodeError, ValidationError, ValueError) as e:
                last_err = e
                if attempt < max_retries:
                    time.sleep(0.5 * (2**attempt))
                    continue
                gen.update(
                    level="ERROR",
                    status_message=str(e),
                    output={"raw_text": raw_text[:500]},
                )
                raise RuntimeError(
                    f"call_structured failed after {max_retries + 1} attempts. "
                    f"Last error: {e}. Raw response: {raw_text[:300]!r}"
                ) from e
        raise RuntimeError(f"unreachable: {last_err}")
