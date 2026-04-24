"""Prompt context decomposition."""

from __future__ import annotations

from helix.context_engine.hasher import SemanticHasher
from helix.context_engine.types import ContextBlock, ContextBlockType, ContextDiff, ContextSnapshot


class ContextDecomposer:
    """Split messages and prompts into typed context blocks."""

    def __init__(self, hasher: SemanticHasher) -> None:
        """Create a decomposer with a hasher."""
        self.hasher = hasher

    def _block(
        self, block_type: ContextBlockType, content: str, step_id: str, run_id: str, position: int
    ) -> ContextBlock:
        tokens = round(len(content.split()) * 1.3)
        return ContextBlock(
            block_type=block_type,
            content=content,
            block_hash=self.hasher.hash_text(content),
            token_estimate=tokens,
            metadata={"step_id": step_id, "run_id": run_id, "position": str(position)},
        )

    def decompose_messages(self, messages: list[dict], step_id: str, run_id: str) -> ContextSnapshot:
        """Split a message list into typed ContextBlocks."""
        blocks: list[ContextBlock] = []
        seen_assistant = False
        first_user = True
        for pos, message in enumerate(messages):
            role = str(message.get("role", ""))
            content = str(message.get("content", ""))
            if role == "system":
                block_type = ContextBlockType.SYSTEM
            elif role in {"tool", "function"}:
                block_type = ContextBlockType.TOOL_RESULT
            elif role == "assistant":
                block_type = ContextBlockType.HISTORY
                seen_assistant = True
            elif role == "user" and first_user and not seen_assistant:
                block_type = ContextBlockType.STATIC_PREFIX
                first_user = False
            elif role == "user" and seen_assistant:
                block_type = ContextBlockType.HISTORY
            elif role == "user":
                block_type = ContextBlockType.DYNAMIC_CONTENT
            else:
                block_type = ContextBlockType.UNKNOWN
            blocks.append(self._block(block_type, content, step_id, run_id, pos))
        total = sum(block.token_estimate for block in blocks)
        return ContextSnapshot(step_id, run_id, blocks, total, self.hasher.hash_blocks(blocks))

    def decompose_string(self, prompt: str, step_id: str, run_id: str) -> ContextSnapshot:
        """Single-string prompt: entire prompt is one STATIC_PREFIX block."""
        block = self._block(ContextBlockType.STATIC_PREFIX, prompt, step_id, run_id, 0)
        return ContextSnapshot(step_id, run_id, [block], block.token_estimate, self.hasher.hash_blocks([block]))

    def diff(self, snapshot_a: ContextSnapshot, snapshot_b: ContextSnapshot) -> ContextDiff:
        """Compute changed, added, and removed blocks by block hash."""
        a = {block.block_hash: block for block in snapshot_a.blocks}
        b = {block.block_hash: block for block in snapshot_b.blocks}
        added = [block for key, block in b.items() if key not in a]
        removed = [block for key, block in a.items() if key not in b]
        unchanged = [block for key, block in b.items() if key in a]
        denom = max(1, len(snapshot_b.blocks))
        return ContextDiff(added, removed, unchanged, (len(added) + len(removed)) / denom)

