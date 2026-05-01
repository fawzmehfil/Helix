from __future__ import annotations

from dataclasses import dataclass

from typing_extensions import TypedDict

import pytest

pytest.importorskip("langgraph")

from langgraph.graph import END, START, StateGraph

from helix.adapters.langgraph import HelixLangGraphRunner, helix_langgraph
from helix.adapters.langgraph.llm_wrapper import helix_openai_call
from helix.adapters.langgraph.utils import compute_summary, project_node_input
from helix.execution_optimizer.types import ExecutionDecisionType


class SupportState(TypedDict, total=False):
    ticket: str
    tone: str
    style: str
    facts: str
    response: str
    debug_info: str
    region: str


class ToneInput(TypedDict):
    tone: str


class TicketInput(TypedDict):
    ticket: str


@dataclass
class FakeUsage:
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int


@dataclass
class FakeOpenAIResponse:
    usage: FakeUsage
    model: str = "gpt-4o-mini"


def _fake_openai_create(prompt_tokens: int = 10, completion_tokens: int = 5) -> FakeOpenAIResponse:
    return FakeOpenAIResponse(
        usage=FakeUsage(
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
        )
    )


def test_langgraph_adapter_reuses_unchanged_node_and_recomputes_changed_path():
    calls: list[str] = []

    def classify_tone(state: ToneInput) -> dict[str, str]:
        calls.append("classify_tone")
        helix_openai_call(_fake_openai_create, prompt_tokens=7, completion_tokens=3)
        return {"style": f"{state['tone']} support"}

    def extract_facts(state: TicketInput) -> dict[str, str]:
        calls.append("extract_facts")
        helix_openai_call(_fake_openai_create, prompt_tokens=11, completion_tokens=4)
        return {"facts": state["ticket"].lower()}

    def draft_response(state: SupportState) -> dict[str, str]:
        calls.append("draft_response")
        helix_openai_call(_fake_openai_create, prompt_tokens=13, completion_tokens=5)
        return {"response": f"{state['style']}: {state['facts']}"}

    builder = StateGraph(SupportState)
    builder.add_node("classify_tone", classify_tone, input_schema=ToneInput)
    builder.add_node("extract_facts", extract_facts, input_schema=TicketInput)
    builder.add_node("draft_response", draft_response)
    builder.add_edge(START, "classify_tone")
    builder.add_edge(START, "extract_facts")
    builder.add_edge("classify_tone", "draft_response")
    builder.add_edge("extract_facts", "draft_response")
    builder.add_edge("draft_response", END)

    runner = HelixLangGraphRunner(builder.compile())

    first = runner.invoke({"ticket": "Refund request for invoice 100", "tone": "friendly"})
    first_events = {event.step_id: event.decision for event in runner.last_run_events}
    first_calls = list(calls)
    calls.clear()

    second = runner.invoke({"ticket": "Refund request for invoice 200", "tone": "friendly"})
    second_events = {event.step_id: event.decision for event in runner.last_run_events}
    trace = runner.get_trace()
    summary = compute_summary(trace)
    trace_json = runner.get_trace_json()
    metrics = runner.get_metrics_summary()
    cache_trace = next(entry for entry in trace if entry.decision == "cache_hit")

    assert first["response"] == "friendly support: refund request for invoice 100"
    assert second["response"] == "friendly support: refund request for invoice 200"
    assert first_calls.count("classify_tone") == 1
    assert calls == ["extract_facts", "draft_response"]
    assert first_events == {
        "classify_tone": ExecutionDecisionType.EXECUTE,
        "extract_facts": ExecutionDecisionType.EXECUTE,
        "draft_response": ExecutionDecisionType.EXECUTE,
    }
    assert second_events["classify_tone"] == ExecutionDecisionType.CACHE_HIT
    assert second_events["extract_facts"] == ExecutionDecisionType.EXECUTE
    assert second_events["draft_response"] == ExecutionDecisionType.EXECUTE
    assert len(trace) == 3
    assert {entry.decision for entry in trace} >= {"cache_hit", "execute"}
    assert cache_trace.input_hash
    assert cache_trace.reason == "input unchanged"
    assert any(entry.reason.startswith("input changed:") for entry in trace)
    assert summary == {
        "total_nodes": 3,
        "nodes_reused": 1,
        "nodes_executed": 2,
        "reuse_rate": 1 / 3,
        "estimated_calls_avoided": 1,
    }
    assert trace_json["summary"] == summary
    assert len(trace_json["trace"]) == 3
    assert trace_json["trace"][0]["step_id"] == trace[0].step_id
    assert metrics["calls_made"] == 2
    assert metrics["calls_avoided"] == 1
    assert metrics["total_calls"] == 2
    assert metrics["input_tokens"] == 24
    assert metrics["output_tokens"] == 9
    assert metrics["total_tokens"] == 33
    assert metrics["tokens"] == 33
    assert metrics["cost_usd"] > 0
    assert metrics["latency_ms"] > 0
    assert runner.get_node_metrics()["classify_tone"]["calls_made"] == 0
    assert runner.get_node_metrics()["classify_tone"]["calls_avoided"] == 1
    assert runner.get_node_metrics()["extract_facts"]["calls_made"] == 1
    assert trace_json["metrics"] == metrics


def test_helix_langgraph_helper_wraps_builder_and_preserves_trace():
    calls: list[str] = []

    def classify_tone(state: ToneInput) -> dict[str, str]:
        calls.append("classify_tone")
        return {"style": f"{state['tone']} support"}

    builder = StateGraph(SupportState)
    builder.add_node("classify_tone", classify_tone, input_schema=ToneInput)
    builder.add_edge(START, "classify_tone")
    builder.add_edge("classify_tone", END)

    runner = helix_langgraph(builder)

    first = runner.invoke({"tone": "friendly"})
    calls.clear()
    second = runner.invoke({"tone": "friendly"})

    assert first["style"] == "friendly support"
    assert second["style"] == "friendly support"
    assert calls == []
    assert runner.get_trace()[0].step_id == "classify_tone"
    assert runner.get_trace()[0].decision == "cache_hit"
    assert isinstance(runner, HelixLangGraphRunner)


def test_helix_langgraph_helper_wraps_compiled_graph():
    def classify_tone(state: ToneInput) -> dict[str, str]:
        return {"style": f"{state['tone']} support"}

    builder = StateGraph(SupportState)
    builder.add_node("classify_tone", classify_tone, input_schema=ToneInput)
    builder.add_edge(START, "classify_tone")
    builder.add_edge("classify_tone", END)

    runner = helix_langgraph(builder.compile())
    result = runner.invoke({"tone": "calm"})

    assert result["style"] == "calm support"
    assert isinstance(runner, HelixLangGraphRunner)


def test_langgraph_without_node_inputs_keeps_full_state_cache_behavior():
    calls: list[str] = []

    def summarize(state: SupportState) -> dict[str, str]:
        calls.append("summarize")
        return {"response": f"{state['ticket']} / {state.get('debug_info', '')}"}

    builder = StateGraph(SupportState)
    builder.add_node("summarize", summarize)
    builder.add_edge(START, "summarize")
    builder.add_edge("summarize", END)
    runner = helix_langgraph(builder)

    runner.invoke({"ticket": "invoice 100", "debug_info": "a"})
    calls.clear()
    runner.invoke({"ticket": "invoice 100", "debug_info": "b"})

    assert calls == ["summarize"]
    assert runner.get_trace()[0].decision == "execute"
    assert runner.get_trace()[0].reason == "input changed: debug_info"


def test_langgraph_node_inputs_ignore_unrelated_state_and_recompute_relevant_fields():
    calls: list[str] = []

    def summarize(state: SupportState) -> dict[str, str]:
        calls.append("summarize")
        return {"response": f"{state['ticket']} / {state.get('debug_info', '')}"}

    builder = StateGraph(SupportState)
    builder.add_node("summarize", summarize)
    builder.add_edge(START, "summarize")
    builder.add_edge("summarize", END)
    runner = helix_langgraph(builder, node_inputs={"summarize": ["ticket"]})

    first = runner.invoke({"ticket": "invoice 100", "debug_info": "a"})
    calls.clear()
    second = runner.invoke({"ticket": "invoice 100", "debug_info": "b"})
    third = runner.invoke({"ticket": "invoice 200", "debug_info": "b"})

    assert first["response"] == "invoice 100 / a"
    assert second["response"] == "invoice 100 / a"
    assert third["response"] == "invoice 200 / b"
    assert calls == ["summarize"]
    assert runner.get_trace()[0].decision == "execute"
    assert runner.get_trace()[0].reason == "input changed: ticket"


def test_langgraph_node_inputs_missing_fields_are_stable_none_values():
    calls: list[str] = []

    def summarize(state: SupportState) -> dict[str, str]:
        calls.append("summarize")
        return {"response": state["ticket"]}

    builder = StateGraph(SupportState)
    builder.add_node("summarize", summarize)
    builder.add_edge(START, "summarize")
    builder.add_edge("summarize", END)
    runner = helix_langgraph(builder, node_inputs={"summarize": ["ticket", "region"]})

    assert project_node_input({"ticket": "invoice 100"}, ["ticket", "region"]) == {
        "ticket": "invoice 100",
        "region": None,
    }
    runner.invoke({"ticket": "invoice 100", "debug_info": "a"})
    first_hash = runner.get_trace()[0].input_hash
    calls.clear()
    runner.invoke({"ticket": "invoice 100", "debug_info": "b"})
    second_hash = runner.get_trace()[0].input_hash

    assert calls == []
    assert first_hash == second_hash
    assert runner.get_trace()[0].decision == "cache_hit"
