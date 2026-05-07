import json
import os
from collections.abc import Callable, Awaitable

import anthropic
from anthropic import AsyncAnthropic
from anthropic.types import MessageParam, ToolParam, ToolUseBlock, TextBlock
from mcp import types as mcp_types

from .models import AgentResponse, ToolCall
from .exceptions import MissingAnthropicKeyError, MaxIterationsError

DEFAULT_MODEL = "claude-sonnet-4-6"
DEFAULT_MAX_ITERATIONS = 10
DEFAULT_TEMPERATURE = 0.0


class NavdocAgent:
    """High-level ask() — Claude tool_use loop."""

    def __init__(self, anthropic_api_key: str | None = None) -> None:
        key = anthropic_api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise MissingAnthropicKeyError(
                "Anthropic API key is required for ask(). "
                "Pass anthropic_api_key= or set ANTHROPIC_API_KEY env var."
            )
        self._client = AsyncAnthropic(api_key=key)

    async def ask(
        self,
        question: str,
        mcp_tools: list[mcp_types.Tool],
        call_tool_fn: Callable[[str, dict], Awaitable[dict]],
        *,
        system_prompt: str = "",
        model: str = DEFAULT_MODEL,
        tool_args: dict[str, dict] | None = None,
        temperature: float = DEFAULT_TEMPERATURE,
        max_iterations: int = DEFAULT_MAX_ITERATIONS,
    ) -> AgentResponse:
        tools = self._convert_tools(mcp_tools)
        messages: list[MessageParam] = [{"role": "user", "content": question}]
        collected_tool_calls: list[ToolCall] = []
        total_input_tokens = 0
        total_output_tokens = 0

        for _ in range(max_iterations):
            kwargs: dict = dict(
                model=model,
                max_tokens=4096,
                tools=tools,
                messages=messages,
                temperature=temperature,
            )
            if system_prompt:
                kwargs["system"] = system_prompt

            response = await self._client.messages.create(**kwargs)
            total_input_tokens += response.usage.input_tokens
            total_output_tokens += response.usage.output_tokens

            if response.stop_reason != "tool_use":
                return AgentResponse(
                    answer=self._extract_text(response),
                    tool_calls=collected_tool_calls,
                    model=response.model,
                    usage={
                        "input_tokens": total_input_tokens,
                        "output_tokens": total_output_tokens,
                    },
                )

            tool_results = []
            for block in response.content:
                if not isinstance(block, ToolUseBlock):
                    continue
                args = dict(block.input)
                for key, val in (tool_args or {}).get(block.name, {}).items():
                    if key not in args:
                        args[key] = val

                tool_output = await call_tool_fn(block.name, args)
                collected_tool_calls.append(
                    ToolCall(name=block.name, input=args, output=tool_output)
                )
                tool_results.append({
                    "type": "tool_result",
                    "tool_use_id": block.id,
                    "content": json.dumps(tool_output, ensure_ascii=False),
                })

            messages.append({"role": "assistant", "content": response.content})
            messages.append({"role": "user", "content": tool_results})

        raise MaxIterationsError(max_iterations)

    def _convert_tools(self, mcp_tools: list[mcp_types.Tool]) -> list[ToolParam]:
        return [
            ToolParam(
                name=tool.name,
                description=tool.description or "",
                input_schema=tool.inputSchema,
            )
            for tool in mcp_tools
        ]

    def _extract_text(self, response) -> str:
        return "\n".join(b.text for b in response.content if isinstance(b, TextBlock))
