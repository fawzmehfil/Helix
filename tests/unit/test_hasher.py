from helix.context_engine import SemanticHasher


def test_hash_text_normalizes():
    assert SemanticHasher().hash_text(" Hello ") == SemanticHasher().hash_text("hello")

