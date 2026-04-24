from helix.api_clients import FakeLLMClient


def test_fake_llm_deterministic():
    messages = [{"role": "user", "content": "hello"}]
    client = FakeLLMClient(sleep_ms=0)
    assert client.call(messages)["content"] == client.call(messages)["content"]

