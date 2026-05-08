import asyncio
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import typer


@dataclass
class Placeholder:
    key: str
    label: str
    default: str = ""


@dataclass
class AskConfig:
    name: str
    description: str
    system_prompt: str
    user_prompt: str | None = None
    placeholders: list[Placeholder] = field(default_factory=list)
    tools: list[str] | None = None


app = typer.Typer(no_args_is_help=True)


@app.callback()
def _callback() -> None:
    """navdoc – MCP-powered RAG client CLI."""


def _make_client() -> "NavdocClient":  # noqa: F821
    from navdoc import NavdocClient

    return NavdocClient()


def _read_json(path: Path) -> dict:
    try:
        text = path.read_text(encoding="utf-8")
    except FileNotFoundError:
        typer.echo(f"Error: config file not found: '{path}'")
        raise typer.Exit(1)
    except PermissionError:
        typer.echo(f"Error: cannot read config file: '{path}'")
        raise typer.Exit(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        typer.echo(f"Error: invalid JSON in '{path}': {e}")
        raise typer.Exit(1)
    if not isinstance(data, dict):
        typer.echo("Error: config must be a JSON object")
        raise typer.Exit(1)
    return data


def _load_config(path: Path) -> AskConfig:
    data = _read_json(path)

    placeholders: list[Placeholder] = []
    for item in data.get("placeholders", []):
        if not isinstance(item, dict) or "key" not in item or "label" not in item:
            typer.echo(f"Error: malformed placeholder entry: {item}")
            raise typer.Exit(1)
        placeholders.append(
            Placeholder(
                key=item["key"],
                label=item["label"],
                default=item.get("default", ""),
            )
        )

    tools = data.get("tools")
    if tools is not None and not isinstance(tools, list):
        typer.echo("Warning: 'tools' must be a list, ignoring.")
        tools = None

    return AskConfig(
        name=data.get("name", ""),
        description=data.get("description", ""),
        system_prompt=data.get("system_prompt", ""),
        user_prompt=data.get("user_prompt"),
        placeholders=placeholders,
        tools=tools,
    )


def _resolve_placeholders(config: AskConfig, overrides: dict[str, str]) -> dict[str, str]:
    resolved: dict[str, str] = {}
    for ph in config.placeholders:
        if ph.key in overrides:
            resolved[ph.key] = overrides[ph.key]
        elif ph.default:
            resolved[ph.key] = ph.default
        else:
            resolved[ph.key] = typer.prompt(ph.label)
    return resolved


def _render_template(template: str, values: dict[str, str]) -> str:
    def replace(m: re.Match) -> str:
        return values.get(m.group(1), m.group(0))

    return re.sub(r"\{\{(\w+)\}\}", replace, template)


@app.command("list-tools")
def list_tools() -> None:
    """List all MCP tools exposed by the navdoc server."""

    async def _run() -> None:
        client = _make_client()
        tools = await client.list_tools()
        for tool in tools:
            desc = tool.description or ""
            typer.echo(f"{tool.name:<28}{desc}")

    asyncio.run(_run())


@app.command("ask")
def ask_cmd(
    config: Path = typer.Option(..., "--config", help="Path to config JSON file."),
    var: list[str] = typer.Option([], help="Placeholder value as key=value."),
) -> None:
    """Run a one-shot ask query defined by a config JSON file."""
    overrides: dict[str, str] = {}
    for item in var:
        if "=" not in item:
            typer.echo(f"Warning: ignoring --var '{item}' (no '=' found)")
            continue
        key, _, value = item.partition("=")
        overrides[key.strip()] = value

    config_obj = _load_config(config)

    if not config_obj.user_prompt:
        typer.echo("Error: config missing required field 'user_prompt'")
        raise typer.Exit(1)

    placeholder_keys = {p.key for p in config_obj.placeholders}
    for key in overrides:
        if key not in placeholder_keys:
            typer.echo(f"Warning: --var key '{key}' not found in placeholders, ignoring.")

    resolved = _resolve_placeholders(config_obj, overrides)
    question = _render_template(config_obj.user_prompt, resolved)
    system_prompt = _render_template(config_obj.system_prompt, resolved)

    async def _run() -> None:
        from navdoc.exceptions import MissingAnthropicKeyError, NavdocError

        try:
            client = _make_client()
            response = await client.ask(
                question,
                system_prompt=system_prompt,
                tools=config_obj.tools,
            )
        except MissingAnthropicKeyError:
            typer.echo(
                "Error: ANTHROPIC_API_KEY is not set.\n"
                "Export it with: export ANTHROPIC_API_KEY=sk-ant-..."
            )
            raise typer.Exit(1)
        except (NavdocError, ValueError) as e:
            typer.echo(f"Error: {e}")
            raise typer.Exit(1)

        typer.echo(response.answer)

    asyncio.run(_run())


@app.command("chat")
def chat_cmd(
    config: Path = typer.Option(..., "--config", help="Path to config JSON file."),
    var: list[str] = typer.Option([], help="Placeholder value as key=value."),
    no_initial_message: bool = typer.Option(
        False, "--no-initial-message", help="Do not send user_prompt as the first message."
    ),
) -> None:
    """Start an interactive multi-turn chat session."""
    overrides: dict[str, str] = {}
    for item in var:
        if "=" not in item:
            typer.echo(f"Warning: ignoring --var '{item}' (no '=' found)")
            continue
        key, _, value = item.partition("=")
        overrides[key.strip()] = value

    config_obj = _load_config(config)

    placeholder_keys = {p.key for p in config_obj.placeholders}
    for key in overrides:
        if key not in placeholder_keys:
            typer.echo(f"Warning: --var key '{key}' not found in placeholders, ignoring.")

    typer.echo("Chat started. Type 'exit' or press Ctrl+C to quit.\n")

    history: list = []

    async def _send(question: str) -> str:
        from navdoc.exceptions import MissingAnthropicKeyError, NavdocError

        try:
            client = _make_client()
            response = await client.ask(
                question,
                messages=history,
                system_prompt=config_obj.system_prompt,
                tools=config_obj.tools,
            )
        except MissingAnthropicKeyError:
            typer.echo(
                "Error: ANTHROPIC_API_KEY is not set.\n"
                "Export it with: export ANTHROPIC_API_KEY=sk-ant-..."
            )
            raise typer.Exit(1)
        except (NavdocError, ValueError) as e:
            typer.echo(f"Error: {e}")
            raise typer.Exit(1)
        return response.answer

    def turn(question: str) -> None:
        answer = asyncio.run(_send(question))
        typer.echo(f"\nClaude: {answer}\n")
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer})

    if config_obj.user_prompt and not no_initial_message:
        resolved = _resolve_placeholders(config_obj, overrides)
        question = _render_template(config_obj.user_prompt, resolved)
        typer.echo(f"You: {question}")
        turn(question)

    while True:
        try:
            user_input = typer.prompt("You")
        except (KeyboardInterrupt, EOFError):
            typer.echo("\nBye.")
            break
        if user_input.strip().lower() in {"exit", "quit"}:
            typer.echo("Bye.")
            break
        if not user_input.strip():
            continue
        turn(user_input)


def main() -> None:
    app()
