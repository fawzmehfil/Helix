from helix.context_engine import ContextDecomposer, SemanticHasher
from helix.kv_simulator import KVSimulator, ModelSpec


def test_kv_overlap():
    d = ContextDecomposer(SemanticHasher())
    a = d.decompose_string("same prefix", "a", "r")
    b = d.decompose_string("same prefix", "b", "r")
    est = KVSimulator({"fake": ModelSpec("fake", 60, 0.1, 0, 0)}).estimate(a, b, "fake")
    assert est.prefix_overlap_tokens == b.total_tokens

