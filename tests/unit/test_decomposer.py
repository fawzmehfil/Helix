from helix.context_engine import ContextBlockType, ContextDecomposer, SemanticHasher


def test_decompose_messages_types():
    snap = ContextDecomposer(SemanticHasher()).decompose_messages(
        [{"role": "system", "content": "S"}, {"role": "user", "content": "U"}], "s", "r"
    )
    assert [b.block_type for b in snap.blocks] == [ContextBlockType.SYSTEM, ContextBlockType.STATIC_PREFIX]
    assert snap.total_tokens >= 2

