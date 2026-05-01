"""LLM call metrics helpers for the LangGraph adapter."""

from __future__ import annotations

import time
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any, Callable, Iterator

from helix.benchmark_engine.cost import estimate_cost_usd


@dataclass
class LLMCallMetrics:
    """Measured metrics from one LLM API response."""

    calls_made: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    cost_usd: float = 0.0
    latency_ms: float = 0.0


MetricsRecorder = Callable[[LLMCallMetrics], None]
_metrics_recorder: ContextVar[MetricsRecorder | None] = ContextVar(
    "helix_langgraph_metrics_recorder",
    default=None,
)


@contextmanager
def capture_helix_metrics(recorder: MetricsRecorder) -> Iterator[None]:
    """Capture wrapper metrics produced inside this context."""
    token = _metrics_recorder.set(recorder)
    try:
        yield
    finally:
        _metrics_recorder.reset(token)


def _usage_value(usage: Any, *names: str) -> int:
    for name in names:
        if isinstance(usage, dict):
            value = usage.get(name)
        else:
            value = getattr(usage, name, None)
        if value is not None:
            return int(value)
    return 0


def _response_value(response: Any, name: str) -> Any:
    if isinstance(response, dict):
        return response.get(name)
    return getattr(response, name, None)


def _extract_metrics(response: Any, model: str | None, latency_ms: float) -> LLMCallMetrics | None:
    usage = _response_value(response, "usage")
    if usage is None:
        return None
    input_tokens = _usage_value(usage, "prompt_tokens", "input_tokens")
    output_tokens = _usage_value(usage, "completion_tokens", "output_tokens")
    total_tokens = _usage_value(usage, "total_tokens")
    if total_tokens == 0:
        total_tokens = input_tokens + output_tokens
    if total_tokens == 0:
        return None
    model_id = model or _response_value(response, "model") or ""
    return LLMCallMetrics(
        calls_made=1,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        total_tokens=total_tokens,
        cost_usd=estimate_cost_usd(str(model_id), input_tokens, output_tokens),
        latency_ms=latency_ms,
    )


def helix_openai_call(call: Callable[..., Any], *args: Any, **kwargs: Any) -> Any:
    """Call an OpenAI API method and record actual response usage when available."""
    model = kwargs.get("model")
    started = time.perf_counter()
    response = call(*args, **kwargs)
    latency_ms = (time.perf_counter() - started) * 1000
    metrics = _extract_metrics(response, model, latency_ms)
    recorder = _metrics_recorder.get()
    if metrics is not None and recorder is not None:
        recorder(metrics)
    return response
