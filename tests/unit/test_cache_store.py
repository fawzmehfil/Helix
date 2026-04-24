import datetime as dt

from helix.cache_engine import CacheEntry, CacheKey, CachePolicy, CacheStore
from helix.context_engine import ContextDecomposer, SemanticHasher


def test_cache_store_put_get_clear(cache_db_path):
    store = CacheStore(cache_db_path, CachePolicy())
    snap = ContextDecomposer(SemanticHasher()).decompose_string("hello", "s", "r")
    key = CacheKey(snap.blocks, "fake")
    store.put(key, CacheEntry(key.key, "s", "r", {"content": "x"}, 1, 1, 1.0, dt.datetime.utcnow(), None))
    assert store.get(key).response["content"] == "x"
    assert store.clear() == 1

