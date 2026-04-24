from helix.context_engine import ContextDecomposer, SemanticHasher
from helix.kv_simulator import KVSimulator, ModelSpec


def test_kv_overlap():
    d = ContextDecomposer(SemanticHasher())
    a = d.decompose_string("same prefix", "a", "r")
    b = d.decompose_string("same prefix", "b", "r")
    est = KVSimulator({"fake": ModelSpec("fake", 60, 0.1, 0, 0)}).estimate(a, b, "fake")
    assert est.prefix_overlap_tokens == b.total_tokens


def test_kv_shared_system_prefix_overlap():
    d = ContextDecomposer(SemanticHasher())
    a = d.decompose_messages(
        [
            {"role": "system", "content": "Shared stable system prompt."},
            {"role": "user", "content": "Explain cache reuse."},
        ],
        "a",
        "r",
    )
    b = d.decompose_messages(
        [
            {"role": "system", "content": "Shared stable system prompt."},
            {"role": "user", "content": "Explain graph reuse."},
        ],
        "b",
        "r",
    )
    est = KVSimulator({"fake": ModelSpec("fake", 60, 0.1, 0, 0)}).estimate(a, b, "fake")
    assert est.prefix_overlap_tokens > 0
    assert est.prefix_overlap_tokens < b.total_tokens


def test_kv_different_context_low_overlap():
    d = ContextDecomposer(SemanticHasher())
    a = d.decompose_messages(
        [
            {"role": "system", "content": "Shared stable system prompt."},
            {"role": "user", "content": "Explain cache reuse."},
        ],
        "a",
        "r",
    )
    b = d.decompose_messages(
        [
            {"role": "system", "content": "Completely different instructions."},
            {"role": "user", "content": "Discuss unrelated content."},
        ],
        "b",
        "r",
    )
    est = KVSimulator({"fake": ModelSpec("fake", 60, 0.1, 0, 0)}).estimate(a, b, "fake")
    assert est.prefix_overlap_tokens == 0
