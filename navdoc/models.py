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
class AgentTool:
    name: str
    description: str
    input_schema: dict = field(default_factory=dict)


@dataclass
class StreamEvent:
    type: str        # "text" | "tool_use" | "tool_result" | "done" | "error"
    delta: str | None = None    # type=text
    name: str | None = None     # type=tool_use, tool_result
    input: dict | None = None   # type=tool_use, tool_result
    message: str | None = None  # type=error


@dataclass
class TemplatePlaceholder:
    key: str
    label: str
    auto: bool = False
    default: str | None = None


@dataclass
class AgentTemplate:
    id: str
    name: str
    description: str | None
    system_prompt: str | None
    user_prompt: str | None
    placeholders: list[TemplatePlaceholder]
    tools: list[str] | None
    greeting: str | None
    required_scope_description: str | None
    is_public: bool
    star_count: int
    is_starred: bool
    is_mine: bool
    temperature: float | None = None
