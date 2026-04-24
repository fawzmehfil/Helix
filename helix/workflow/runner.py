"""Workflow execution runner."""

from __future__ import annotations

import json
import re
import time
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

from helix.api_clients.protocols import LLMClient, ToolClient
from helix.benchmark_engine.collector import BenchmarkCollector
from helix.config import HelixConfig
from helix.execution_optimizer.optimizer import ExecutionOptimizer
from helix.execution_optimizer.types import ExecutionDecision, ExecutionDecisionType, OptimizationPlan
from helix.workflow.types import RunResult, StepResult, Workflow, WorkflowStepType


class WorkflowRunner:
    """Execute Helix workflows in baseline or optimized mode."""

    def __init__(
        self,
        optimizer: ExecutionOptimizer,
        llm_client: LLMClient,
        tool_client: ToolClient,
        benchmark_collector: BenchmarkCollector,
        baseline_mode: bool = False,
    ) -> None:
        """Create a workflow runner."""
        self.optimizer = optimizer
        self.llm_client = llm_client
        self.tool_client = tool_client
        self.benchmark_collector = benchmark_collector
        self.baseline_mode = baseline_mode

    def _resolve_text(self, text: str, inputs: dict[str, str], outputs: dict[str, dict]) -> str:
        def repl(match: re.Match[str]) -> str:
            key = match.group(1)
            if key.endswith(".output"):
                step_id = key[:-7]
                return str(outputs.get(step_id, {}).get("content", ""))
            return str(inputs.get(key, ""))

        return re.sub(r"\{([A-Za-z0-9_.-]+)\}", repl, text)

    def _resolve_value(self, value: Any, inputs: dict[str, str], outputs: dict[str, dict]) -> Any:
        if isinstance(value, str):
            return self._resolve_text(value, inputs, outputs)
        if isinstance(value, list):
            return [self._resolve_value(item, inputs, outputs) for item in value]
        if isinstance(value, dict):
            return {key: self._resolve_value(item, inputs, outputs) for key, item in value.items()}
        return value

    def _resolve_workflow(self, workflow: Workflow, inputs: dict[str, str], outputs: dict[str, dict]) -> Workflow:
        resolved = deepcopy(workflow)
        for step in resolved.steps:
            for message in step.messages:
                message["content"] = self._resolve_text(str(message.get("content", "")), inputs, outputs)
            if step.tool_args is not None:
                step.tool_args = self._resolve_value(step.tool_args, inputs, outputs)
        return resolved

    def _log_run(self, result: RunResult) -> None:
        runs_dir = Path(HelixConfig.default().runs_dir).expanduser()
        runs_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "run_id": result.run_id,
            "workflow_id": result.workflow_id,
            "baseline_mode": result.baseline_mode,
            "total_latency_ms": result.total_latency_ms,
            "steps": [
                {
                    "step_id": step.step_id,
                    "decision": step.decision.value,
                    "input_tokens": step.input_tokens,
                    "output_tokens": step.output_tokens,
                    "latency_ms": step.latency_ms,
                    "kv_prefix_overlap_tokens": step.kv_estimate.prefix_overlap_tokens
                    if step.kv_estimate
                    else 0,
                    "kv_reused_fraction": step.kv_estimate.reused_fraction
                    if step.kv_estimate
                    else 0.0,
                }
                for step in result.step_results
            ],
        }
        (runs_dir / f"{result.run_id}.json").write_text(json.dumps(payload, indent=2))

    def run(
        self,
        workflow: Workflow,
        inputs: dict[str, str],
        run_id: Optional[str] = None,
    ) -> RunResult:
        """Run a workflow and return aggregate results."""
        run_id = run_id or str(uuid.uuid4())
        outputs: dict[str, dict] = {}
        step_results: list[StepResult] = []
        decisions: list[ExecutionDecision] = []
        estimated_time_saved_ms = 0.0
        estimated_cost_saved_usd = 0.0
        if self.baseline_mode:
            for index, step in enumerate(workflow.steps):
                resolved = self._resolve_workflow(workflow, inputs, outputs)
                current = next(s for s in resolved.steps if s.step_id == step.step_id)
                partial = deepcopy(resolved)
                partial.steps = [resolved.steps[index]]
                step_plan = self.optimizer.plan(partial, run_id)
                decision = step_plan.decisions[0]
                decisions.append(decision)
                estimated_time_saved_ms += step_plan.estimated_total_time_saved_ms
                estimated_cost_saved_usd += step_plan.estimated_total_cost_saved_usd
                started = time.perf_counter()
                if current.step_type == WorkflowStepType.TOOL_CALL:
                    tool_response = self.tool_client.call(current.tool_name or "echo", current.tool_args or {})
                    response = {"content": str(tool_response["result"]), "input_tokens": 0, "output_tokens": 0, "model": current.model, "finish_reason": "tool", "raw": tool_response}
                else:
                    response = self.llm_client.call(current.messages)
                latency = float(response.get("latency_ms", (time.perf_counter() - started) * 1000))
                self.optimizer.record_execution(decision, response, latency)
                result = StepResult(current.step_id, ExecutionDecisionType.EXECUTE, response, int(response.get("input_tokens", 0)), int(response.get("output_tokens", 0)), latency, None, False, False)
                outputs[current.step_id] = response
                step_results.append(result)
                self.benchmark_collector.record_step(result)
        else:
            for index, original_step in enumerate(workflow.steps):
                resolved = self._resolve_workflow(workflow, inputs, outputs)
                partial = deepcopy(resolved)
                partial.steps = [resolved.steps[index]]
                step_plan = self.optimizer.plan(partial, run_id)
                decision = step_plan.decisions[0]
                decisions.append(decision)
                estimated_time_saved_ms += step_plan.estimated_total_time_saved_ms
                estimated_cost_saved_usd += step_plan.estimated_total_cost_saved_usd
                current = partial.steps[0]
                if decision.decision == ExecutionDecisionType.CACHE_HIT and decision.cache_entry:
                    response = decision.cache_entry.response
                    latency = 0.0
                elif decision.decision == ExecutionDecisionType.GRAPH_REUSE and decision.graph_node:
                    response = decision.graph_node.response
                    latency = 0.0
                else:
                    started = time.perf_counter()
                    if current.step_type == WorkflowStepType.TOOL_CALL:
                        tool_response = self.tool_client.call(current.tool_name or "echo", current.tool_args or {})
                        response = {"content": str(tool_response["result"]), "input_tokens": 0, "output_tokens": 0, "model": current.model, "finish_reason": "tool", "raw": tool_response}
                    else:
                        response = self.llm_client.call(current.messages)
                    latency = float(response.get("latency_ms", (time.perf_counter() - started) * 1000))
                    self.optimizer.record_execution(decision, response, latency)
                result = StepResult(
                    current.step_id,
                    decision.decision,
                    response,
                    0 if decision.decision != ExecutionDecisionType.EXECUTE else int(response.get("input_tokens", 0)),
                    0 if decision.decision != ExecutionDecisionType.EXECUTE else int(response.get("output_tokens", 0)),
                    latency,
                    decision.kv_estimate,
                    decision.decision == ExecutionDecisionType.CACHE_HIT,
                    decision.decision == ExecutionDecisionType.GRAPH_REUSE,
                )
                outputs[current.step_id] = response
                step_results.append(result)
                self.benchmark_collector.record_step(result)
        plan = OptimizationPlan(
            run_id,
            workflow.workflow_id,
            decisions,
            estimated_time_saved_ms,
            estimated_cost_saved_usd,
        )
        result = RunResult(
            run_id=run_id,
            workflow_id=workflow.workflow_id,
            step_results=step_results,
            total_latency_ms=sum(step.latency_ms for step in step_results),
            total_input_tokens=sum(step.input_tokens for step in step_results),
            total_output_tokens=sum(step.output_tokens for step in step_results),
            optimization_plan=plan,
            baseline_mode=self.baseline_mode,
        )
        self._log_run(result)
        return result
