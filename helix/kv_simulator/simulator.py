"""KV-cache savings simulator."""

from __future__ import annotations

from typing import Optional

from helix.context_engine.types import ContextSnapshot
from helix.kv_simulator.types import KVReuseEstimate, ModelSpec


class KVSimulator:
    """Estimate KV-cache reuse from block-level prefix overlap."""

    def __init__(self, model_specs: dict[str, ModelSpec]) -> None:
        """Create a simulator with model specs."""
        self.model_specs = model_specs

    def estimate(
        self,
        prev_snapshot: Optional[ContextSnapshot],
        curr_snapshot: ContextSnapshot,
        model_id: str,
    ) -> KVReuseEstimate:
        """Compute prefix overlap between prev and curr snapshots."""
        spec = self.model_specs.get(
            model_id,
            ModelSpec(model_id, 60.0, 0.1, 0.0, 0.0),
        )
        overlap = 0
        if prev_snapshot is not None:
            for prev, curr in zip(prev_snapshot.blocks, curr_snapshot.blocks):
                if prev.block_hash != curr.block_hash:
                    break
                overlap += curr.token_estimate
        total = max(1, curr_snapshot.total_tokens)
        factor = 1.0 - spec.cache_hit_multiplier
        return KVReuseEstimate(
            step_id=curr_snapshot.step_id,
            prefix_overlap_tokens=overlap,
            reused_fraction=overlap / total,
            estimated_time_saved_ms=(overlap / spec.tokens_per_second) * 1000.0 * factor,
            estimated_cost_saved_usd=(overlap / 1000.0) * spec.cost_per_1k_input_tokens * factor,
            model_id=model_id,
        )

    def bulk_estimate(
        self,
        snapshots: list[tuple[Optional[ContextSnapshot], ContextSnapshot]],
        model_id: str,
    ) -> list[KVReuseEstimate]:
        """Estimate KV reuse for many snapshot pairs."""
        return [self.estimate(prev, curr, model_id) for prev, curr in snapshots]

