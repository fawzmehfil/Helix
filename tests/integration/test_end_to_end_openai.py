import pytest

from helix.api_clients import OpenAIClient


@pytest.mark.skipif(not OpenAIClient().is_available(), reason="No OpenAI key")
def test_end_to_end_openai_available():
    assert OpenAIClient().is_available()

