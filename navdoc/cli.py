import asyncio
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import typer
from rich import box
from rich.console import Console
from rich.markdown import Markdown
from rich.panel import Panel
from rich.prompt import Prompt
from rich.rule import Rule
from rich.table import Table

console = Console()


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
        console.print(f"[bold red]Error:[/bold red] config file not found: '{path}'")
        raise typer.Exit(1)
    except PermissionError:
        console.print(f"[bold red]Error:[/bold red] cannot read config file: '{path}'")
        raise typer.Exit(1)
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        console.print(f"[bold red]Error:[/bold red] invalid JSON in '{path}': {e}")
        raise typer.Exit(1)
    if not isinstance(data, dict):
        console.print("[bold red]Error:[/bold red] config must be a JSON object")
        raise typer.Exit(1)
    return data


def _load_config(path: Path) -> AskConfig:
    data = _read_json(path)

    placeholders: list[Placeholder] = []
    for item in data.get("placeholders", []):
        if not isinstance(item, dict) or "key" not in item or "label" not in item:
            console.print(f"[bold red]Error:[/bold red] malformed placeholder entry: {item}")
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
        console.print("[yellow]Warning:[/yellow] 'tools' must be a list, ignoring.")
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
            resolved[ph.key] = Prompt.ask(ph.label)
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
        table = Table(box=box.SIMPLE, show_header=True, header_style="bold")
        table.add_column("Tool", style="green")
        table.add_column("Description")
        for tool in tools:
            table.add_row(tool.name, tool.description or "")
        console.print(table)

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
            console.print(f"[yellow]Warning:[/yellow] ignoring --var '{item}' (no '=' found)")
            continue
        key, _, value = item.partition("=")
        overrides[key.strip()] = value

    config_obj = _load_config(config)

    if not config_obj.user_prompt:
        console.print("[bold red]Error:[/bold red] config missing required field 'user_prompt'")
        raise typer.Exit(1)

    placeholder_keys = {p.key for p in config_obj.placeholders}
    for key in overrides:
        if key not in placeholder_keys:
            console.print(f"[yellow]Warning:[/yellow] --var key '{key}' not found in placeholders, ignoring.")

    resolved = _resolve_placeholders(config_obj, overrides)
    question = _render_template(config_obj.user_prompt, resolved)
    system_prompt = _render_template(config_obj.system_prompt, resolved)

    async def _run() -> str:
        from navdoc.exceptions import MissingAnthropicKeyError, NavdocError

        try:
            client = _make_client()
            response = await client.ask(
                question,
                system_prompt=system_prompt,
                tools=config_obj.tools,
            )
        except MissingAnthropicKeyError:
            console.print(
                "[bold red]Error:[/bold red] ANTHROPIC_API_KEY is not set.\n"
                "Export it with: export ANTHROPIC_API_KEY=sk-ant-..."
            )
            raise typer.Exit(1)
        except (NavdocError, ValueError) as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            raise typer.Exit(1)
        return response.answer

    with console.status("Thinking…"):
        answer = asyncio.run(_run())

    console.print(Markdown(answer))


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
            console.print(f"[yellow]Warning:[/yellow] ignoring --var '{item}' (no '=' found)")
            continue
        key, _, value = item.partition("=")
        overrides[key.strip()] = value

    config_obj = _load_config(config)

    placeholder_keys = {p.key for p in config_obj.placeholders}
    for key in overrides:
        if key not in placeholder_keys:
            console.print(f"[yellow]Warning:[/yellow] --var key '{key}' not found in placeholders, ignoring.")

    console.print(Rule("navdoc chat"))
    console.print("[dim]Chat started. Type 'exit' or press Ctrl+C to quit.[/dim]\n")

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
            console.print(
                "[bold red]Error:[/bold red] ANTHROPIC_API_KEY is not set.\n"
                "Export it with: export ANTHROPIC_API_KEY=sk-ant-..."
            )
            raise typer.Exit(1)
        except (NavdocError, ValueError) as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            raise typer.Exit(1)
        return response.answer

    def turn(question: str) -> None:
        status = console.status("Thinking…")
        status.start()
        try:
            answer = asyncio.run(_send(question))
        finally:
            status.stop()
        console.print(Panel(Markdown(answer), title="Claude", border_style="cyan"))
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer})

    try:
        if config_obj.user_prompt and not no_initial_message:
            resolved = _resolve_placeholders(config_obj, overrides)
            question = _render_template(config_obj.user_prompt, resolved)
            console.print(f"[bold green]You:[/bold green] {question}")
            turn(question)

        while True:
            try:
                user_input = Prompt.ask("[bold green]You[/bold green]")
            except (KeyboardInterrupt, EOFError):
                console.print("\n[dim]Bye.[/dim]")
                break
            if user_input.strip().lower() in {"exit", "quit"}:
                console.print("[dim]Bye.[/dim]")
                break
            if not user_input.strip():
                continue
            turn(user_input)
    finally:
        console.show_cursor(True)


def main() -> None:
    app()
