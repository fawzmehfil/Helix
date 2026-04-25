"""Workflow execution runner."""

from __future__ import annotations

import json
import re
import time
import uuid
from copy import deepcopy
from pathlib import Path
from typing import Any, Optional

from helix.benchmark_engine.cost import estimate_cost_usd
from helix.api_clients.protocols import LLMClient, ToolClient
from helix.benchmark_engine.collector import BenchmarkCollector
from helix.config import HelixConfig
from helix.execution_optimizer.optimizer import ExecutionOptimizer
from helix.execution_optimizer.types import ExecutionDecision, ExecutionDecisionType, OptimizationPlan
from helix.tokenization import TokenCounter
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
        self.token_counter = TokenCounter(getattr(llm_client, "model_id", "fake"))

    def _estimate_tokens(self, messages: list[dict]) -> int:
        return self.token_counter.count_messages(messages)

    def _compact_json(self, value: Any) -> str:
        return json.dumps(value, separators=(",", ":"), sort_keys=True)

    def _coerce_output_content(self, response: dict) -> Any:
        content = response.get("content", "")
        if isinstance(content, (dict, list)):
            return content
        if isinstance(content, str):
            try:
                return json.loads(content)
            except json.JSONDecodeError:
                return content
        return content

    def _get_path_value(self, value: Any, path: str) -> Any:
        current = value
        for part in path.split("."):
            if isinstance(current, dict):
                current = current.get(part, "")
            else:
                return ""
        return current

    def _truncate_text(self, text: str, spec: dict[str, Any]) -> str:
        if "max_chars" in spec:
            return text[: int(spec["max_chars"])]
        if "max_words" in spec:
            return " ".join(text.split()[: int(spec["max_words"])])
        if spec.get("mode") == "first_sentence" or spec.get("first_sentence"):
            match = re.search(r"(.+?[.!?])(?:\s|$)", text)
            return match.group(1) if match else text.split("\n", 1)[0]
        return text

    def _project_response(self, step_id: str, response: dict, projection: dict[str, dict[str, Any]]) -> str:
        spec = projection.get(step_id)
        content = self._coerce_output_content(response)
        if not spec:
            return self._compact_json(content) if isinstance(content, (dict, list)) else str(content)
        fields = spec.get("fields", [])
        if isinstance(content, dict):
            selected = {
                field: self._get_path_value(content, field)
                for field in fields
                if self._get_path_value(content, field) != ""
            }
            return self._compact_json(selected)
        return self._truncate_text(str(content), spec)

    def _resolve_text(
        self,
        text: str,
        inputs: dict[str, str],
        outputs: dict[str, dict],
        projection: dict[str, dict[str, Any]] | None = None,
        apply_field_slicing: bool = True,
    ) -> str:
        projection = projection or {}

        def repl(match: re.Match[str]) -> str:
            key = match.group(1)
            if ".output." in key:
                step_id, field = key.split(".output.", 1)
                if not apply_field_slicing:
                    return self._project_response(step_id, outputs.get(step_id, {}), {})
                content = self._coerce_output_content(outputs.get(step_id, {}))
                if isinstance(content, dict):
                    value = self._get_path_value(content, field)
                    return self._compact_json(value) if isinstance(value, (dict, list)) else str(value)
                return ""
            if key.endswith(".output"):
                step_id = key[:-7]
                return self._project_response(step_id, outputs.get(step_id, {}), projection)
            return str(inputs.get(key, ""))

        return re.sub(r"\{([A-Za-z0-9_.-]+)\}", repl, text)

    def _resolve_value(
        self,
        value: Any,
        inputs: dict[str, str],
        outputs: dict[str, dict],
        projection: dict[str, dict[str, Any]] | None = None,
        apply_field_slicing: bool = True,
    ) -> Any:
        if isinstance(value, str):
            return self._resolve_text(value, inputs, outputs, projection, apply_field_slicing)
        if isinstance(value, list):
            return [
                self._resolve_value(item, inputs, outputs, projection, apply_field_slicing)
                for item in value
            ]
        if isinstance(value, dict):
            return {
                key: self._resolve_value(item, inputs, outputs, projection, apply_field_slicing)
                for key, item in value.items()
            }
        return value

    def _structured_consumers(self, workflow: Workflow) -> set[str]:
        consumers: set[str] = set()
        for step in workflow.steps:
            consumers.update(step.input_projection.keys())
            for message in step.messages:
                content = str(message.get("content", ""))
                for match in re.finditer(r"\{([A-Za-z0-9_.-]+)\}", content):
                    key = match.group(1)
                    if ".output." in key:
                        consumers.add(key.split(".output.", 1)[0])
        return consumers

    def _apply_compact_instructions(self, step, structured_consumers: set[str]) -> None:
        if not step.compact:
            return
        if step.output_format == "json" and not (
            step.step_id in structured_consumers and (step.required_fields or step.output_schema)
        ):
            return
        instruction = "Be concise."
        if step.output_format == "json":
            instruction = "Return compact JSON only."
        if step.messages and step.messages[0].get("role") == "system":
            step.messages[0]["content"] = f"{step.messages[0].get('content', '')} {instruction}"
        else:
            step.messages.insert(0, {"role": "system", "content": instruction})

    def _resolve_workflow(
        self,
        workflow: Workflow,
        inputs: dict[str, str],
        outputs: dict[str, dict],
        use_projection: bool = False,
        apply_compact: bool = False,
        apply_field_slicing: bool = True,
    ) -> Workflow:
        resolved = deepcopy(workflow)
        structured_consumers = self._structured_consumers(workflow)
        for step in resolved.steps:
            projection = step.input_projection if use_projection else {}
            for message in step.messages:
                message["content"] = self._resolve_text(
                    str(message.get("content", "")),
                    inputs,
                    outputs,
                    projection,
                    apply_field_slicing,
                )
            if step.tool_args is not None:
                step.tool_args = self._resolve_value(
                    step.tool_args,
                    inputs,
                    outputs,
                    projection,
                    apply_field_slicing,
                )
            if apply_compact:
                self._apply_compact_instructions(step, structured_consumers)
        return resolved

    def _minimize_step_context(self, step) -> None:
        if "minimize_context" not in step.tags:
            return
        for message in step.messages:
            content = " ".join(str(message.get("content", "")).split())
            words = content.split()
            if len(words) > 80:
                content = " ".join(words[:80])
            message["content"] = content

    def _apply_prompt_budget(self, step, messages: list[dict]) -> tuple[list[dict], int, bool]:
        if step.max_dependency_tokens is None and step.max_input_tokens is None:
            return messages, 0, False
        if not step.depends_on:
            return messages, 0, False
        trimmed = deepcopy(messages)
        before = self._estimate_tokens(trimmed)
        applied = False
        if step.max_dependency_tokens is not None:
            for message in trimmed:
                content = str(message.get("content", ""))
                if "{" in content or message.get("role") == "system":
                    continue
                words = content.split()
                limit = int(step.max_dependency_tokens / 1.3)
                if len(words) > limit:
                    message["content"] = " ".join(words[:limit])
                    applied = True
        if step.max_input_tokens is not None:
            while self._estimate_tokens(trimmed) > step.max_input_tokens:
                candidates = [m for m in trimmed if m.get("role") != "system"]
                if not candidates:
                    break
                target = max(candidates, key=lambda item: len(str(item.get("content", "")).split()))
                words = str(target.get("content", "")).split()
                if len(words) <= 1:
                    break
                target["content"] = " ".join(words[:-1])
                applied = True
        after = self._estimate_tokens(trimmed)
        return trimmed, max(0, before - after), applied

    def _messages_fingerprint(self, messages: list[dict]) -> str:
        return json.dumps(messages, sort_keys=True)

    def _call_step(self, current) -> dict:
        if current.step_type == WorkflowStepType.TOOL_CALL:
            tool_response = self.tool_client.call(current.tool_name or "echo", current.tool_args or {})
            return {
                "content": self._compact_json(tool_response["result"]),
                "input_tokens": 0,
                "output_tokens": 0,
                "model": current.model,
                "finish_reason": "tool",
                "raw": tool_response,
            }
        kwargs = {}
        if current.max_output_tokens is not None:
            kwargs["max_tokens"] = int(current.max_output_tokens)
        return self.llm_client.call(current.messages, **kwargs)

    def _validate_structured_response(self, current, response: dict) -> bool:
        if current.output_format != "json":
            return True
        content = response.get("content", "")
        try:
            parsed = json.loads(content) if isinstance(content, str) else content
        except json.JSONDecodeError:
            return False
        if not isinstance(parsed, dict):
            return False
        if current.output_schema:
            return self._validate_json_schema(parsed, current.output_schema)
        return all(field in parsed for field in current.required_fields)

    def _validate_json_schema(self, value: Any, schema: dict[str, Any]) -> bool:
        schema_type = schema.get("type")
        if schema_type == "object":
            if not isinstance(value, dict):
                return False
            required = schema.get("required", [])
            if any(field not in value for field in required):
                return False
            properties = schema.get("properties", {})
            return all(
                field not in value or self._validate_json_schema(value[field], field_schema)
                for field, field_schema in properties.items()
            )
        if schema_type == "array":
            if not isinstance(value, list):
                return False
            item_schema = schema.get("items")
            return all(self._validate_json_schema(item, item_schema) for item in value) if item_schema else True
        if schema_type == "string":
            return isinstance(value, str)
        if schema_type == "number":
            return isinstance(value, int | float) and not isinstance(value, bool)
        if schema_type == "integer":
            return isinstance(value, int) and not isinstance(value, bool)
        if schema_type == "boolean":
            return isinstance(value, bool)
        return True

    def _repair_structured_response(self, current, response: dict) -> tuple[dict, bool, bool, bool]:
        if current.output_format != "json" or self._validate_structured_response(current, response):
            return response, False, False, False
        schema = current.output_schema or {
            "type": "object",
            "required": current.required_fields,
            "properties": {field: {"type": "string"} for field in current.required_fields},
        }
        repair_messages = [
            {
                "role": "system",
                "content": "Fix this JSON to match schema exactly. Return ONLY valid JSON.",
            },
            {
                "role": "user",
                "content": self._compact_json(
                    {
                        "schema": schema,
                        "invalid_response": response.get("content", ""),
                    }
                ),
            },
        ]
        repair_response = self.llm_client.call(repair_messages, max_tokens=current.max_output_tokens or 128)
        successful = self._validate_structured_response(current, repair_response)
        if successful:
            merged = dict(repair_response)
            merged["latency_ms"] = float(response.get("latency_ms", 0.0)) + float(
                repair_response.get("latency_ms", 0.0)
            )
            merged["input_tokens"] = int(response.get("input_tokens", 0)) + int(
                repair_response.get("input_tokens", 0)
            )
            merged["output_tokens"] = int(response.get("output_tokens", 0)) + int(
                repair_response.get("output_tokens", 0)
            )
            return merged, True, True, False
        failed = dict(response)
        failed["structured_output_error"] = "invalid_json"
        return failed, True, False, True

    def _step_result(
        self,
        current,
        decision_type: ExecutionDecisionType,
        response: dict,
        input_tokens: int,
        output_tokens: int,
        latency: float,
        kv_estimate,
        cache_hit: bool,
        graph_reuse: bool,
        raw_messages: list[dict],
        minimized_messages: list[dict],
        projection_messages: list[dict] | None = None,
        tokens_trimmed_by_budget: int = 0,
        budget_applied: bool = False,
        projection_declared: bool = False,
        repair_attempted: bool = False,
        repair_successful: bool = False,
        structured_output_failed: bool = False,
        semantic_cache_hit: bool = False,
        semantic_reuse_applied: bool = False,
        similarity_score: float = 0.0,
    ) -> StepResult:
        model = str(response.get("model", current.model))
        raw_input_tokens = self._estimate_tokens(raw_messages)
        minimized_input_tokens = self._estimate_tokens(minimized_messages)
        projected_tokens = self._estimate_tokens(projection_messages or minimized_messages)
        optimization_overhead_tokens = max(0, minimized_input_tokens - projected_tokens)
        tokens_removed_by_projection = max(0, raw_input_tokens - projected_tokens)
        net_tokens_saved = raw_input_tokens - minimized_input_tokens
        warnings = []
        if projection_declared and minimized_input_tokens > raw_input_tokens:
            warnings.append("Context minimization regression: optimized prompt larger than raw prompt")
        if projection_declared and projected_tokens >= raw_input_tokens:
            warnings.append("Projection ineffective: no reduction in context")
        if projection_declared and optimization_overhead_tokens > tokens_removed_by_projection:
            warnings.append("Optimization overhead exceeded projection savings")
        return StepResult(
            step_id=current.step_id,
            decision=decision_type,
            response=response,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            latency_ms=latency,
            kv_estimate=kv_estimate,
            cache_hit=cache_hit,
            graph_reuse=graph_reuse,
            model=model,
            estimated_cost_usd=estimate_cost_usd(model, input_tokens, output_tokens),
            call_count=(
                1 + int(repair_attempted)
                if current.step_type == WorkflowStepType.LLM_CALL
                and decision_type == ExecutionDecisionType.EXECUTE
                else 0
            ),
            raw_input_tokens=raw_input_tokens,
            projected_input_tokens=projected_tokens,
            minimized_input_tokens=minimized_input_tokens,
            tokens_removed_by_projection=tokens_removed_by_projection,
            optimization_overhead_tokens=optimization_overhead_tokens,
            net_tokens_saved_by_minimization=net_tokens_saved,
            minimization_effective=net_tokens_saved > 0,
            tokens_trimmed_by_budget=tokens_trimmed_by_budget,
            budget_applied=budget_applied,
            minimization_warnings=warnings,
            tokens_saved_by_minimization=max(0, raw_input_tokens - minimized_input_tokens),
            net_token_change=minimized_input_tokens - raw_input_tokens,
            raw_messages=raw_messages,
            minimized_messages=minimized_messages,
            repair_attempted=repair_attempted,
            repair_successful=repair_successful,
            structured_output_failed=structured_output_failed,
            schema_validation_failed=structured_output_failed,
            semantic_cache_hit=semantic_cache_hit,
            semantic_reuse_applied=semantic_reuse_applied,
            similarity_score=similarity_score,
        )

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
                    "raw_input_tokens": step.raw_input_tokens,
                    "projected_input_tokens": step.projected_input_tokens,
                    "minimized_input_tokens": step.minimized_input_tokens,
                    "tokens_removed_by_projection": step.tokens_removed_by_projection,
                    "optimization_overhead_tokens": step.optimization_overhead_tokens,
                    "net_tokens_saved_by_minimization": step.net_tokens_saved_by_minimization,
                    "tokens_trimmed_by_budget": step.tokens_trimmed_by_budget,
                    "budget_applied": step.budget_applied,
                    "minimization_effective": step.minimization_effective,
                    "repair_attempted": step.repair_attempted,
                    "repair_successful": step.repair_successful,
                    "schema_validation_failed": step.schema_validation_failed,
                    "semantic_cache_hit": step.semantic_cache_hit,
                    "similarity_score": step.similarity_score,
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
        reusable_responses: dict[str, dict] = {}
        step_results: list[StepResult] = []
        decisions: list[ExecutionDecision] = []
        estimated_time_saved_ms = 0.0
        estimated_cost_saved_usd = 0.0
        if self.baseline_mode:
            for index, step in enumerate(workflow.steps):
                resolved = self._resolve_workflow(
                    workflow,
                    inputs,
                    outputs,
                    apply_field_slicing=False,
                )
                current = next(s for s in resolved.steps if s.step_id == step.step_id)
                partial = deepcopy(resolved)
                partial.steps = [resolved.steps[index]]
                current = partial.steps[0]
                raw_messages = deepcopy(current.messages)
                step_plan = self.optimizer.plan(partial, run_id)
                decision = step_plan.decisions[0]
                decisions.append(decision)
                estimated_time_saved_ms += step_plan.estimated_total_time_saved_ms
                estimated_cost_saved_usd += step_plan.estimated_total_cost_saved_usd
                started = time.perf_counter()
                response = self._call_step(current)
                response, repair_attempted, repair_successful, structured_failed = (
                    self._repair_structured_response(current, response)
                )
                latency = float(response.get("latency_ms", (time.perf_counter() - started) * 1000))
                self.optimizer.record_execution(decision, response, latency)
                input_tokens = int(response.get("input_tokens", 0))
                output_tokens = int(response.get("output_tokens", 0))
                result = self._step_result(
                    current,
                    ExecutionDecisionType.EXECUTE,
                    response,
                    input_tokens,
                    output_tokens,
                    latency,
                    None,
                    False,
                    False,
                    raw_messages,
                    raw_messages,
                    raw_messages,
                    False,
                    repair_attempted,
                    repair_successful,
                    structured_failed,
                )
                outputs[current.step_id] = response
                step_results.append(result)
                self.benchmark_collector.record_step(result)
        else:
            for index, _original_step in enumerate(workflow.steps):
                raw_resolved = self._resolve_workflow(
                    workflow,
                    inputs,
                    outputs,
                    apply_field_slicing=False,
                )
                raw_current = raw_resolved.steps[index]
                projected_resolved = self._resolve_workflow(
                    workflow,
                    inputs,
                    outputs,
                    use_projection=True,
                    apply_compact=False,
                )
                resolved = self._resolve_workflow(
                    workflow,
                    inputs,
                    outputs,
                    use_projection=True,
                    apply_compact=True,
                )
                partial = deepcopy(resolved)
                partial.steps = [resolved.steps[index]]
                current = partial.steps[0]
                if not self.baseline_mode:
                    self._minimize_step_context(current)
                budget_messages, tokens_trimmed_by_budget, budget_applied = self._apply_prompt_budget(
                    current,
                    current.messages,
                )
                current.messages = budget_messages
                raw_messages = deepcopy(raw_current.messages)
                projection_messages = deepcopy(projected_resolved.steps[index].messages)
                minimized_messages = deepcopy(current.messages)
                fingerprint = self._messages_fingerprint(current.messages)
                if "eliminate_if_duplicate" in current.tags and fingerprint in reusable_responses:
                    response = reusable_responses[fingerprint]
                    decision = ExecutionDecision(
                        current.step_id,
                        ExecutionDecisionType.SKIP,
                        reason="duplicate resolved step eliminated at runtime",
                    )
                    decisions.append(decision)
                    result = self._step_result(
                        current,
                        ExecutionDecisionType.SKIP,
                        response,
                        0,
                        0,
                        0.0,
                        None,
                        False,
                        False,
                        raw_messages,
                        minimized_messages,
                        projection_messages,
                        tokens_trimmed_by_budget,
                        budget_applied,
                        bool(current.input_projection),
                    )
                    outputs[current.step_id] = response
                    step_results.append(result)
                    self.benchmark_collector.record_step(result)
                    continue
                step_plan = self.optimizer.plan(partial, run_id)
                decision = step_plan.decisions[0]
                decisions.append(decision)
                estimated_time_saved_ms += step_plan.estimated_total_time_saved_ms
                estimated_cost_saved_usd += step_plan.estimated_total_cost_saved_usd
                if decision.decision == ExecutionDecisionType.CACHE_HIT and decision.cache_entry:
                    response = decision.cache_entry.response
                    latency = 0.0
                elif decision.decision == ExecutionDecisionType.GRAPH_REUSE and decision.graph_node:
                    response = decision.graph_node.response
                    latency = 0.0
                else:
                    started = time.perf_counter()
                    response = self._call_step(current)
                    response, repair_attempted, repair_successful, structured_failed = (
                        self._repair_structured_response(current, response)
                    )
                    latency = float(response.get("latency_ms", (time.perf_counter() - started) * 1000))
                    self.optimizer.record_execution(decision, response, latency)
                if decision.decision != ExecutionDecisionType.EXECUTE:
                    repair_attempted = False
                    repair_successful = False
                    structured_failed = False
                input_tokens = (
                    0
                    if decision.decision != ExecutionDecisionType.EXECUTE
                    else int(response.get("input_tokens", 0))
                )
                output_tokens = (
                    0
                    if decision.decision != ExecutionDecisionType.EXECUTE
                    else int(response.get("output_tokens", 0))
                )
                result = self._step_result(
                    current,
                    decision.decision,
                    response,
                    input_tokens,
                    output_tokens,
                    latency,
                    decision.kv_estimate,
                    decision.decision == ExecutionDecisionType.CACHE_HIT,
                    decision.decision == ExecutionDecisionType.GRAPH_REUSE,
                    raw_messages,
                    minimized_messages,
                    projection_messages,
                    tokens_trimmed_by_budget,
                    budget_applied,
                    bool(current.input_projection),
                    repair_attempted,
                    repair_successful,
                    structured_failed,
                    decision.semantic_cache_hit,
                    decision.semantic_reuse_applied,
                    decision.similarity_score,
                )
                outputs[current.step_id] = response
                reusable_responses[fingerprint] = response
                step_results.append(result)
                self.benchmark_collector.record_step(result)
                if (
                    workflow.metadata.get("early_stop_after_step") == current.step_id
                    and str(response.get("content", "")).strip()
                ):
                    break
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
