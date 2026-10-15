from backend.agent.agent_loop import AGENT_TEMPERATURE, _assistant_tool_call_message


def test_agent_temperature_is_low_and_stable():
    assert AGENT_TEMPERATURE == 0.2


def test_tool_call_without_preamble_uses_null_content():
    message = _assistant_tool_call_message(
        {"content_parts": []},
        [{"id": "call-1", "name": "news_list", "arguments": '{"limit":20}'}],
    )

    assert message == {
        "role": "assistant",
        "content": None,
        "tool_calls": [{
            "id": "call-1",
            "type": "function",
            "function": {"name": "news_list", "arguments": '{"limit":20}'},
        }],
    }


def test_tool_call_preserves_non_empty_preamble():
    message = _assistant_tool_call_message(
        {"content_parts": ["我先查询新闻。"]},
        [{"id": "call-1", "name": "news_list", "arguments": "{}"}],
    )

    assert message["content"] == "我先查询新闻。"
