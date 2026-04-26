from helix.embeddings import HashEmbeddingProvider, cosine_similarity


def test_hash_embedding_similarity_for_near_duplicate_company_names():
    provider = HashEmbeddingProvider()

    left = provider.embed("Summarize invoice for Acme Corp")
    right = provider.embed("Summarize invoice for ACME Corporation")

    assert cosine_similarity(left, right) >= 0.90


def test_hash_embedding_similarity_rejects_dissimilar_text():
    provider = HashEmbeddingProvider()

    left = provider.embed("Summarize invoice for Acme Corp")
    right = provider.embed("Classify a legal contract dispute")

    assert cosine_similarity(left, right) < 0.90
