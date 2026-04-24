from helix.cache_engine import CacheKey
from helix.context_engine import ContextDecomposer, SemanticHasher


def test_cache_key_stable():
    snap = ContextDecomposer(SemanticHasher()).decompose_string("hello", "s", "r")
    assert CacheKey(snap.blocks, "fake") == CacheKey(snap.blocks, "fake")

