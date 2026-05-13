import asyncio
import json
import re
from dataclasses import dataclass, field
from pathlib import Path

import typer
from prompt_toolkit import prompt as pt_prompt
from prompt_toolkit.formatted_text import HTML
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.key_binding import KeyBindings
from rich.console import Console
from rich.prompt import Prompt
from rich.rule import Rule

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


app = typer.Typer(no_args_is_help=True)


@app.callback()
def _callback() -> None:
    """navdoc – RAG chat CLI."""


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

    return AskConfig(
        name=data.get("name", ""),
        description=data.get("description", ""),
        system_prompt=data.get("system_prompt", ""),
        user_prompt=data.get("user_prompt"),
        placeholders=placeholders,
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


@app.command("ask")
def ask_cmd(
    question: str | None = typer.Argument(None, help="Question to ask directly."),
    config: Path | None = typer.Option(None, "--config", help="Path to config JSON file."),
    var: list[str] = typer.Option([], help="Placeholder value as key=value."),
    system_prompt_opt: str = typer.Option("", "--system-prompt", help="System prompt (used without --config)."),
) -> None:
    """Run a one-shot ask query."""
    if question is not None and config is not None:
        console.print("[bold red]Error:[/bold red] cannot use both QUESTION argument and --config.")
        raise typer.Exit(1)
    if question is None and config is None:
        console.print("[bold red]Error:[/bold red] provide a QUESTION argument or --config.")
        raise typer.Exit(1)

    if question is not None:
        final_question = question
        final_system_prompt = system_prompt_opt
    else:
        overrides: dict[str, str] = {}
        for item in var:
            if "=" not in item:
                console.print(f"[yellow]Warning:[/yellow] ignoring --var '{item}' (no '=' found)")
                continue
            key, _, value = item.partition("=")
            overrides[key.strip()] = value

        config_obj = _load_config(config)  # type: ignore[arg-type]

        if not config_obj.user_prompt:
            console.print("[bold red]Error:[/bold red] config missing required field 'user_prompt'")
            raise typer.Exit(1)

        placeholder_keys = {p.key for p in config_obj.placeholders}
        for key in overrides:
            if key not in placeholder_keys:
                console.print(f"[yellow]Warning:[/yellow] --var key '{key}' not found in placeholders, ignoring.")

        resolved = _resolve_placeholders(config_obj, overrides)
        final_question = _render_template(config_obj.user_prompt, resolved)
        final_system_prompt = _render_template(config_obj.system_prompt, resolved)

    async def _run() -> None:
        from navdoc.exceptions import NavdocError

        try:
            client = _make_client()
            async for event in client.stream(final_question, system_prompt=final_system_prompt):
                if event.type == "text" and event.delta:
                    console.print(event.delta, end="")
            console.print()
        except (NavdocError, ValueError) as e:
            console.print(f"[bold red]Error:[/bold red] {e}")
            raise typer.Exit(1)

    asyncio.run(_run())


@app.command("chat")
def chat_cmd(
    config: Path | None = typer.Option(None, "--config", help="Path to config JSON file."),
    var: list[str] = typer.Option([], help="Placeholder value as key=value."),
    system_prompt_opt: str = typer.Option("", "--system-prompt", help="System prompt (used when --config is not provided)."),
    no_initial_message: bool = typer.Option(
        False, "--no-initial-message", help="Do not send user_prompt as the first message."
    ),
) -> None:
    """Start an interactive multi-turn chat session."""
    if config is not None:
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
    else:
        overrides = {}
        config_obj = AskConfig(name="", description="", system_prompt=system_prompt_opt)

    console.print(Rule("navdoc chat"))
    console.print("[dim]Chat started. Press Enter to send, Ctrl+J or Esc+Enter for newline. Type 'exit' or Ctrl+C to quit.[/dim]\n")

    history: list = []

    async def _send(question: str) -> str:
        from navdoc.exceptions import NavdocError

        try:
            client = _make_client()
            text_parts: list[str] = []
            received_text = False
            in_tool_call = False
            with console.status("[dim]thinking…[/dim]") as status:
                async for event in client.stream(
                    question,
                    messages=history,
                    system_prompt=config_obj.system_prompt,
                ):
                    if event.type == "tool_use":
                        in_tool_call = True
                        status.update(f"[dim]{event.name or 'searching'}…[/dim]")
                        if received_text:
                            console.print()
                            status.start()
                    elif event.type == "tool_result":
                        in_tool_call = False
                        if received_text:
                            status.stop()
                        else:
                            status.update("[dim]thinking…[/dim]")
                    elif event.type == "text" and event.delta:
                        if not received_text:
                            status.stop()
                            console.print("[bold cyan]Claude:[/bold cyan] ", end="")
                            received_text = True
                        console.print(event.delta, end="")
                        text_parts.append(event.delta)
            if not received_text:
                console.print("[bold cyan]Claude:[/bold cyan] ", end="")
            console.print()
            return "".join(text_parts)
        except (NavdocError, ValueError) as e:
            console.print(f"\n[bold red]Error:[/bold red] {e}")
            raise typer.Exit(1)

    def turn(question: str) -> None:
        answer = asyncio.run(_send(question))
        history.append({"role": "user", "content": question})
        history.append({"role": "assistant", "content": answer})

    input_history = InMemoryHistory()

    _kb = KeyBindings()

    @_kb.add("enter")
    def _submit(event):
        event.current_buffer.validate_and_handle()

    @_kb.add("c-j")
    @_kb.add("escape", "enter")
    def _newline(event):
        event.current_buffer.insert_text("\n")

    try:
        if config_obj.user_prompt and not no_initial_message:
            resolved = _resolve_placeholders(config_obj, overrides)
            question = _render_template(config_obj.user_prompt, resolved)
            console.print(f"[bold green]You:[/bold green] {question}")
            turn(question)

        while True:
            try:
                user_input = pt_prompt(
                    HTML("<b><ansigreen>You</ansigreen></b>: "),
                    history=input_history,
                    multiline=True,
                    prompt_continuation="... ",
                    key_bindings=_kb,
                )
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
