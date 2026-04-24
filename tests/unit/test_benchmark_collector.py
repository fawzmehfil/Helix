from helix.benchmark_engine import BenchmarkCollector
from helix.execution_optimizer import ExecutionDecisionType
from helix.workflow.types import StepResult


def test_collector_finalize():
    c = BenchmarkCollector()
    c.record_step(StepResult("s", ExecutionDecisionType.EXECUTE, {}, 1, 2, 3, None, False, False))
    result = c.finalize("r", "w", "baseline", None, {"fake": 0})
    assert result.total_tokens == 3

