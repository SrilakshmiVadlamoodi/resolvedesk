from app.llm import _to_anthropic_messages


def test_extracts_system_message_separately():
    system, messages = _to_anthropic_messages([{"role": "system", "content": "be helpful"}])

    assert system == "be helpful"
    assert messages == []


def test_converts_assistant_tool_call_to_tool_use_block():
    system, messages = _to_anthropic_messages(
        [
            {"role": "user", "content": "where's my order"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [{"id": "1", "name": "get_customer_orders", "arguments": {}}],
            },
        ]
    )

    assert messages[0] == {"role": "user", "content": "where's my order"}
    assert messages[1]["role"] == "assistant"
    assert messages[1]["content"] == [
        {"type": "tool_use", "id": "1", "name": "get_customer_orders", "input": {}}
    ]


def test_converts_tool_result_to_user_tool_result_block():
    system, messages = _to_anthropic_messages(
        [{"role": "tool", "tool_call_id": "1", "content": "<tool_result>{}</tool_result>"}]
    )

    assert messages[0] == {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": "1", "content": "<tool_result>{}</tool_result>"}],
    }
