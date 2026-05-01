from __future__ import annotations

from typing_extensions import TypedDict

import pytest

pytest.importorskip("langgraph")

from langgraph.graph import END, START, StateGraph

from helix.adapters.langgraph import HelixLangGraphRunner
from helix.execution_optimizer.types import ExecutionDecisionType


class SupportState(TypedDict, total=False):
    ticket: str
    tone: str
    style: str
    facts: str
    response: str


class ToneInput(TypedDict):
    tone: str


class TicketInput(TypedDict):
    ticket: str


def test_langgraph_adapter_reuses_unchanged_node_and_recomputes_changed_path():
    calls: list[str] = []

    def classify_tone(state: ToneInput) -> dict[str, str]:
        calls.append("classify_tone")
        return {"style": f"{state['tone']} support"}

    def extract_facts(state: TicketInput) -> dict[str, str]:
        calls.append("extract_facts")
        return {"facts": state["ticket"].lower()}

    def draft_response(state: SupportState) -> dict[str, str]:
        calls.append("draft_response")
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
