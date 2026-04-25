from helix.tokenization import TokenCounter


def test_fake_token_counter_matches_fake_client_contract():
    messages = [
        {"role": "system", "content": "Count this"},
        {"role": "user", "content": "and this too"},
    ]

    assert TokenCounter("fake").count_messages(messages) == 6


def test_openai_token_counter_uses_message_structure():
    messages = [
        {"role": "system", "content": "Return JSON."},
        {"role": "user", "content": "Classify invoice."},
    ]

    message_tokens = TokenCounter("gpt-4o-mini").count_messages(messages)
    text_tokens = TokenCounter("gpt-4o-mini").count_text("Return JSON. Classify invoice.")

    assert message_tokens > text_tokens
