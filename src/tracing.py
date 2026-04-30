"""Langfuse instrumentation with graceful degradation.

If LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY are not set, every helper becomes
a no-op so the demo runs end-to-end without an account.

Uses the v3+ OTel-style API: nested context managers create parent/child
observations automatically.
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any, Iterator

try:
    from langfuse import Langfuse
except ImportError:
    Langfuse = None  # type: ignore[assignment,misc]


_client: Any | None = None
_client_initialized = False


def _get_client() -> Any | None:
    global _client, _client_initialized
    if _client_initialized:
        return _client
    _client_initialized = True
    if Langfuse is None:
        return None
    if not (os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")):
        return None
    try:
        _client = Langfuse(
            public_key=os.environ["LANGFUSE_PUBLIC_KEY"],
            secret_key=os.environ["LANGFUSE_SECRET_KEY"],
            host=os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com"),
        )
        return _client
    except Exception:
        return None


class _NullSpan:
    """No-op stand-in when Langfuse is disabled."""

    def update(self, **_: Any) -> None: ...
    def end(self, **_: Any) -> None: ...


@contextmanager
def start_trace(name: str, metadata: dict[str, Any] | None = None) -> Iterator[Any]:
    """Outermost trace. Yield a root span (or a null span)."""
    client = _get_client()
    if client is None:
        yield _NullSpan()
        return
    try:
        with client.start_as_current_observation(
            name=name, as_type="span", metadata=metadata or {}
        ) as span:
            yield span
    except Exception:
        yield _NullSpan()


@contextmanager
def agent_span(name: str, input_payload: Any | None = None) -> Iterator[Any]:
    """Span for one agent's work. Nests under the active trace via OTel context."""
    client = _get_client()
    if client is None:
        yield _NullSpan()
        return
    try:
        with client.start_as_current_observation(
            name=name, as_type="span", input=input_payload
        ) as span:
            yield span
    except Exception:
        yield _NullSpan()


@contextmanager
def llm_generation(
    name: str,
    *,
    model: str,
    input_payload: Any,
) -> Iterator[Any]:
    """Generation observation for a Claude call. Nests under the current agent span."""
    client = _get_client()
    if client is None:
        yield _NullSpan()
        return
    try:
        with client.start_as_current_observation(
            name=name, as_type="generation", model=model, input=input_payload
        ) as gen:
            yield gen
    except Exception:
        yield _NullSpan()


def flush() -> None:
    client = _get_client()
    if client is None:
        return
    try:
        client.flush()
    except Exception:
        pass
