"""Example: optimize a LangGraph support-agent pipeline with Helix."""

from __future__ import annotations

import os
from tempfile import TemporaryDirectory
from typing import Any

from rich.console import Console
from typing_extensions import TypedDict

from helix.adapters.langgraph import HelixLangGraphRunner, helix_langgraph, helix_openai_call
from helix.adapters.langgraph.utils import compute_summary

try:
    from langgraph.graph import END, START, StateGraph
except ImportError as exc:  # pragma: no cover - example-only dependency guard
    raise SystemExit(
        "This example requires LangGraph. Install it with `pip install langgraph`."
    ) from exc


class TicketState(TypedDict, total=False):
    subject: str
    ticket: str
    customer_tier: str
    debug_info: str
    category: str
    context: str
    billing_facts: str
    response: str


class ClassificationInput(TypedDict):
    subject: str


class ContextInput(TypedDict):
    customer_tier: str


class BillingInput(TypedDict):
    ticket: str


def classify_ticket(state: ClassificationInput) -> dict[str, str]:
    subject = state["subject"].lower()
    category = "billing" if "invoice" in subject or "refund" in subject else "general"
    return {"category": category}


def extract_context(state: ContextInput) -> dict[str, str]:
    tier = state["customer_tier"]
    return {"context": f"{tier} customer; prioritize clarity and next steps"}


def extract_billing_facts(state: BillingInput) -> dict[str, str]:
    ticket = state["ticket"].lower()
    facts = "possible duplicate charge" if "charged twice" in ticket else "billing issue"
    return {"billing_facts": facts}


def _openai_text_or_fallback(messages: list[dict[str, str]], fallback: str) -> str:
    if not os.environ.get("OPENAI_API_KEY"):
        return fallback
    try:
        from openai import OpenAI
    except ImportError:
        return fallback
    try:
        client = OpenAI()
        response = helix_openai_call(
            client.chat.completions.create,
            model="gpt-4o-mini",
            messages=messages,
            temperature=0,
        )
    except Exception:
        return fallback
    choices = getattr(response, "choices", [])
    if not choices:
        return fallback
    message: Any = getattr(choices[0], "message", None)
    return str(getattr(message, "content", "") or fallback)


def draft_response(state: TicketState) -> dict[str, str]:
    fallback = (
        f"We classified this as {state['category']}. "
        f"Context: {state['context']}. "
        f"Billing facts: {state['billing_facts']}."
    )
    response = _openai_text_or_fallback(
        [
            {"role": "system", "content": "Draft a concise customer support response."},
            {"role": "user", "content": fallback},
        ],
        fallback,
    )
    return {"response": response}


def build_graph():
    builder = StateGraph(TicketState)
    builder.add_node("classify_ticket", classify_ticket, input_schema=ClassificationInput)
    builder.add_node("extract_context", extract_context, input_schema=ContextInput)
    builder.add_node("extract_billing_facts", extract_billing_facts, input_schema=BillingInput)
    builder.add_node("draft_response", draft_response)
    builder.add_edge(START, "classify_ticket")
    builder.add_edge(START, "extract_context")
    builder.add_edge(START, "extract_billing_facts")
    builder.add_edge("classify_ticket", "draft_response")
    builder.add_edge("extract_context", "draft_response")
    builder.add_edge("extract_billing_facts", "draft_response")
    builder.add_edge("draft_response", END)
    return builder.compile()


def print_run(console: Console, runner: HelixLangGraphRunner, label: str, result: TicketState) -> None:
    console.print(f"\n[bold]{label}[/bold]")
    preview = str(result["response"]).replace("\n", " ")[:96]
    console.print(f"Response preview: {preview}")
    trace = runner.get_trace()
    summary = compute_summary(trace)
    console.print("\n[bold]--- Helix Trace ---[/bold]")
    for entry in trace:
        console.print(f"{entry.step_id} -> {entry.decision} ({entry.reason})")
    console.print("\n[bold]--- Summary ---[/bold]")
    console.print(f"- total nodes: {summary['total_nodes']}")
    console.print(f"- reused: {summary['nodes_reused']}")
    console.print(f"- executed: {summary['nodes_executed']}")
    console.print(f"- reuse rate: {summary['reuse_rate']:.0%}")
    console.print(f"- calls avoided: {summary['estimated_calls_avoided']}")
    metrics = runner.get_metrics_summary()
    console.print("\n[bold]--- Helix Metrics ---[/bold]")
    console.print(f"- calls made: {metrics['calls_made']}")
    console.print(f"- calls avoided: {metrics['calls_avoided']}")
    console.print(f"- tokens used: {metrics['tokens']}")
    console.print(f"- cost: ${metrics['cost_usd']:.6f}")
    console.print(f"- latency: {metrics['latency_ms']:.2f} ms")


def main() -> None:
    console = Console()
    node_inputs = {
        "classify_ticket": ["subject"],
        "extract_context": ["customer_tier"],
        "extract_billing_facts": ["ticket"],
        "draft_response": ["ticket", "category", "context", "billing_facts"],
    }
    first_input = {
        "subject": "Refund request for invoice 100",
        "ticket": "I was charged twice for invoice 100.",
        "customer_tier": "enterprise",
        "debug_info": "first local trace",
    }
    unrelated_change = {
        "subject": "Refund request for invoice 100",
        "ticket": "I was charged twice for invoice 100.",
        "customer_tier": "enterprise",
        "debug_info": "unrelated local trace changed",
    }
    relevant_change = {
        "subject": "Refund request for invoice 100",
        "ticket": "I was charged twice for invoice 200 yesterday.",
        "customer_tier": "enterprise",
        "debug_info": "unrelated local trace changed again",
    }

    with TemporaryDirectory() as tmp_dir:
        runner = helix_langgraph(
            build_graph(),
            cache_path=f"{tmp_dir}/cache.db",
            graph_path=f"{tmp_dir}/graph.db",
            node_inputs=node_inputs,
        )
        first = runner.invoke(first_input)
        print_run(console, runner, "Run 1: original ticket", first)
        second = runner.invoke(unrelated_change)
        print_run(console, runner, "Run 2: unrelated state change", second)
        third = runner.invoke(relevant_change)
        print_run(console, runner, "Run 3: targeted ticket change", third)


if __name__ == "__main__":
    main()
