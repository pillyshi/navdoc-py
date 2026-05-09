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
