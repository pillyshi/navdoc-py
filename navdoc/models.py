from dataclasses import dataclass, field


@dataclass
class ToolCall:
    name: str
    input: dict
    output: dict


@dataclass
class AgentResponse:
    answer: str
    tool_calls: list[ToolCall]
    model: str
    usage: dict  # {"input_tokens": int, "output_tokens": int}


@dataclass
class Document:
    document_id: str
    chunk_count: int


@dataclass
class Scope:
    name: str
    visibility: str  # "private" | "public"


@dataclass
class StreamEvent:
    type: str        # "text" | "tool_use" | "tool_result" | "done" | "error"
    delta: str | None = None    # type=text
    name: str | None = None     # type=tool_use, tool_result
    input: dict | None = None   # type=tool_use, tool_result
    message: str | None = None  # type=error
