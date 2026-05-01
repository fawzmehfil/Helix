"""Example: optimize a LangGraph support-agent pipeline with Helix."""

from __future__ import annotations

from tempfile import TemporaryDirectory

from rich.console import Console
from typing_extensions import TypedDict

from helix.adapters.langgraph import HelixLangGraphRunner
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


def draft_response(state: TicketState) -> dict[str, str]:
    response = (
        f"We classified this as {state['category']}. "
        f"Context: {state['context']}. "
        f"Billing facts: {state['billing_facts']}."
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
    console.print(f"Response: {result['response']}")
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


def main() -> None:
    console = Console()
    first_input = {
        "subject": "Refund request for invoice 100",
        "ticket": "I was charged twice for invoice 100.",
        "customer_tier": "enterprise",
    }
    modified_input = {
        "subject": "Refund request for invoice 100",
        "ticket": "I was charged twice for invoice 100 yesterday.",
        "customer_tier": "enterprise",
    }

    with TemporaryDirectory() as tmp_dir:
        runner = HelixLangGraphRunner(
            build_graph(),
            cache_path=f"{tmp_dir}/cache.db",
            graph_path=f"{tmp_dir}/graph.db",
        )
        first = runner.invoke(first_input)
        print_run(console, runner, "Run 1: original ticket", first)
        second = runner.invoke(modified_input)
        print_run(console, runner, "Run 2: slightly modified ticket", second)


if __name__ == "__main__":
    main()
