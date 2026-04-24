import pytest

from helix.api_clients import AnthropicClient


@pytest.mark.skipif(not AnthropicClient().is_available(), reason="No Anthropic key")
def test_end_to_end_anthropic_available():
    assert AnthropicClient().is_available()

