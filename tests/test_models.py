from navdoc.models import ToolCall, AgentResponse


def test_tool_call_fields():
    tc = ToolCall(name="search", input={"query": "test"}, output={"text": "result"})
    assert tc.name == "search"
    assert tc.input == {"query": "test"}
    assert tc.output == {"text": "result"}


def test_agent_response_fields():
    tc = ToolCall(name="search", input={}, output={})
    resp = AgentResponse(
        answer="answer text",
        tool_calls=[tc],
        model="claude-sonnet-4-6",
        usage={"input_tokens": 100, "output_tokens": 50},
    )
    assert resp.answer == "answer text"
    assert len(resp.tool_calls) == 1
    assert resp.model == "claude-sonnet-4-6"
    assert resp.usage["input_tokens"] == 100


def test_agent_response_empty_tool_calls():
    resp = AgentResponse(
        answer="direct answer",
        tool_calls=[],
        model="claude-sonnet-4-6",
        usage={"input_tokens": 10, "output_tokens": 5},
    )
    assert resp.tool_calls == []
