from app.llm import _to_gemini_contents


def test_extracts_system_instruction_separately():
    system, contents = _to_gemini_contents([{"role": "system", "content": "be helpful"}])

    assert system == "be helpful"
    assert contents == []


def test_converts_user_message():
    system, contents = _to_gemini_contents([{"role": "user", "content": "where's my order"}])

    assert contents == [{"role": "user", "parts": [{"text": "where's my order"}]}]


def test_converts_assistant_tool_call_to_function_call_part():
    system, contents = _to_gemini_contents(
        [
            {"role": "user", "content": "where's my order"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [{"id": "1", "name": "get_customer_orders", "arguments": {}}],
            },
        ]
    )

    assert contents[1]["role"] == "model"
    assert contents[1]["parts"] == [
        {"function_call": {"id": "1", "name": "get_customer_orders", "args": {}}}
    ]


def test_converts_tool_result_to_function_response_part():
    # Gemini's function_response needs the function *name*, not just the call id our
    # agent loop tracks — recovered here from the preceding assistant tool_call.
    system, contents = _to_gemini_contents(
        [
            {"role": "user", "content": "where's my order"},
            {
                "role": "assistant",
                "content": None,
                "tool_calls": [{"id": "1", "name": "get_customer_orders", "arguments": {}}],
            },
            {"role": "tool", "tool_call_id": "1", "content": "<tool_result>{}</tool_result>"},
        ]
    )

    assert contents[2]["role"] == "user"
    assert contents[2]["parts"] == [
        {
            "function_response": {
                "id": "1",
                "name": "get_customer_orders",
                "response": {"content": "<tool_result>{}</tool_result>"},
            }
        }
    ]
