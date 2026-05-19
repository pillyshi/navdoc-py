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
    greeting: str | None = None
    tools: list[str] | None = None
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
        greeting=data.get("greeting"),
        tools=data.get("tools") or None,
        placeholders=placeholders,
    )


def _template_to_config(template) -> AskConfig:
    return AskConfig(
        name=template.name,
        description=template.description or "",
        system_prompt=template.system_prompt or "",
        user_prompt=template.user_prompt,
        greeting=template.greeting,
        tools=template.tools or None,
        placeholders=[
            Placeholder(key=p.key, label=p.label, default=p.default or "")
            for p in template.placeholders
            if not p.auto
        ],
    )


async def _fetch_template_config(template_id: str) -> AskConfig:
    from navdoc.exceptions import NavdocError

    try:
        template = await _make_client().get_template(template_id)
    except NavdocError as e:
        console.print(f"[bold red]Error:[/bold red] could not fetch template '{template_id}': {e}")
        raise typer.Exit(1)
    return _template_to_config(template)


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
    template: str | None = typer.Option(None, "--template", help="Agent template UUID."),
    var: list[str] = typer.Option([], help="Placeholder value as key=value."),
    system_prompt_opt: str = typer.Option("", "--system-prompt", help="System prompt (used without --config/--template)."),
) -> None:
    """Run a one-shot ask query."""
    if config is not None and template is not None:
        console.print("[bold red]Error:[/bold red] --config and --template are mutually exclusive.")
        raise typer.Exit(1)
    if question is not None and (config is not None or template is not None):
        console.print("[bold red]Error:[/bold red] cannot use QUESTION with --config or --template.")
        raise typer.Exit(1)
    if question is None and config is None and template is None:
        console.print("[bold red]Error:[/bold red] provide a QUESTION, --config, or --template.")
        raise typer.Exit(1)

    overrides: dict[str, str] = {}
    if question is None:
        for item in var:
            if "=" not in item:
                console.print(f"[yellow]Warning:[/yellow] ignoring --var '{item}' (no '=' found)")
                continue
            key, _, value = item.partition("=")
            overrides[key.strip()] = value

    final_template_id: str | None = None
    final_tools: list[str] | None = None

    if question is not None:
        final_question = question
        final_system_prompt = system_prompt_opt
    elif config is not None:
        config_obj = _load_config(config)

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
        final_tools = config_obj.tools
    else:  # template is not None
        config_obj = asyncio.run(_fetch_template_config(template))  # type: ignore[arg-type]

        if not config_obj.user_prompt:
            console.print("[bold red]Error:[/bold red] template missing required field 'user_prompt'")
            raise typer.Exit(1)

        placeholder_keys = {p.key for p in config_obj.placeholders}
        for key in overrides:
            if key not in placeholder_keys:
                console.print(f"[yellow]Warning:[/yellow] --var key '{key}' not found in placeholders, ignoring.")

        resolved = _resolve_placeholders(config_obj, overrides)
        final_question = _render_template(config_obj.user_prompt, resolved)
        final_system_prompt = ""
        final_template_id = template

    async def _run() -> None:
        from navdoc.exceptions import NavdocError

        try:
            client = _make_client()
            async for event in client.stream(
                final_question,
                system_prompt=final_system_prompt,
                template_id=final_template_id,
                tools=final_tools,
            ):
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
    template: str | None = typer.Option(None, "--template", help="Agent template UUID."),
    var: list[str] = typer.Option([], help="Placeholder value as key=value."),
    system_prompt_opt: str = typer.Option("", "--system-prompt", help="System prompt (used when --config/--template is not provided)."),
    no_initial_message: bool = typer.Option(
        False, "--no-initial-message", help="Do not send user_prompt as the first message."
    ),
) -> None:
    """Start an interactive multi-turn chat session."""
    if config is not None and template is not None:
        console.print("[bold red]Error:[/bold red] --config and --template are mutually exclusive.")
        raise typer.Exit(1)

    overrides: dict[str, str] = {}
    for item in var:
        if "=" not in item:
            console.print(f"[yellow]Warning:[/yellow] ignoring --var '{item}' (no '=' found)")
            continue
        key, _, value = item.partition("=")
        overrides[key.strip()] = value

    active_template_id: str | None = None

    if config is not None:
        config_obj = _load_config(config)
        placeholder_keys = {p.key for p in config_obj.placeholders}
        for key in overrides:
            if key not in placeholder_keys:
                console.print(f"[yellow]Warning:[/yellow] --var key '{key}' not found in placeholders, ignoring.")
    elif template is not None:
        config_obj = asyncio.run(_fetch_template_config(template))
        active_template_id = template
        placeholder_keys = {p.key for p in config_obj.placeholders}
        for key in overrides:
            if key not in placeholder_keys:
                console.print(f"[yellow]Warning:[/yellow] --var key '{key}' not found in placeholders, ignoring.")
    else:
        config_obj = AskConfig(name="", description="", system_prompt=system_prompt_opt)

    console.print(Rule("navdoc chat"))
    console.print("[dim]Chat started. Press Enter to send, Ctrl+J or Esc+Enter for newline. Type 'exit' or Ctrl+C to quit.[/dim]\n")

    history: list = []

    async def _send(question: str) -> str:
        from navdoc.exceptions import NavdocError

        try:
            client = _make_client()
            pre_tool_text: list[str] = []
            post_tool_text: list[str] = []
            has_tool_call = False
            with console.status("[dim]thinking…[/dim]") as status:
                async for event in client.stream(
                    question,
                    messages=history,
                    system_prompt="" if active_template_id else config_obj.system_prompt,
                    template_id=active_template_id,
                    tools=None if active_template_id else config_obj.tools,
                ):
                    if event.type == "tool_use":
                        has_tool_call = True
                        post_tool_text.clear()
                        status.update(f"[dim]{event.name or 'searching'}…[/dim]")
                    elif event.type == "tool_result":
                        status.update("[dim]thinking…[/dim]")
                    elif event.type == "text" and event.delta:
                        if has_tool_call:
                            post_tool_text.append(event.delta)
                        else:
                            pre_tool_text.append(event.delta)
            final_parts = post_tool_text if has_tool_call else pre_tool_text
            console.print(f"[bold cyan]Claude:[/bold cyan] {''.join(final_parts)}")
            return "".join(final_parts)
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
        if config_obj.greeting and not no_initial_message:
            console.print(f"[bold cyan]Claude:[/bold cyan] {config_obj.greeting}")
            history.append({"role": "assistant", "content": config_obj.greeting})

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


template_app = typer.Typer(no_args_is_help=True)
app.add_typer(template_app, name="template", help="Manage agent templates.")


@template_app.callback()
def _template_callback() -> None:
    """Manage agent templates."""


@template_app.command("list")
def template_list_cmd() -> None:
    """List available agent templates."""
    from navdoc.exceptions import NavdocError

    async def _run():
        return await _make_client().list_templates()

    try:
        templates = asyncio.run(_run())
    except (NavdocError, ValueError) as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)

    if not templates:
        console.print("[dim]No templates found.[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("ID", style="dim", no_wrap=True)
    table.add_column("Name")
    table.add_column("Stars", justify="right")
    table.add_column("Mine", justify="center")
    table.add_column("Public", justify="center")

    for t in templates:
        table.add_row(
            t.id,
            t.name,
            str(t.star_count),
            "Y" if t.is_mine else "-",
            "Y" if t.is_public else "-",
        )

    console.print(table)


@template_app.command("create")
def template_create_cmd(
    config_path: Path = typer.Argument(..., help="Path to local config JSON file."),
    public: bool = typer.Option(False, "--public/--private", help="Set template visibility."),
) -> None:
    """Create a template from a local config JSON file."""
    from navdoc.exceptions import NavdocError

    data = _read_json(config_path)

    api_placeholders = []
    for item in data.get("placeholders", []):
        if not isinstance(item, dict) or "key" not in item or "label" not in item:
            console.print(f"[bold red]Error:[/bold red] malformed placeholder entry: {item}")
            raise typer.Exit(1)
        api_placeholders.append({
            "key": item["key"],
            "label": item["label"],
            "default": item.get("default"),
            "auto": False,
        })

    payload = {
        "name": data.get("name", ""),
        "description": data.get("description"),
        "system_prompt": data.get("system_prompt"),
        "user_prompt": data.get("user_prompt"),
        "greeting": data.get("greeting"),
        "required_scope_description": data.get("required_scope_description"),
        "placeholders": api_placeholders or None,
        "tools": data.get("tools"),
        "is_public": public,
    }

    async def _run():
        return await _make_client().create_template(payload)

    try:
        result = asyncio.run(_run())
    except (NavdocError, ValueError) as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)

    console.print(f"Created template: {result.id}")


@template_app.command("update")
def template_update_cmd(
    template_id: str = typer.Argument(..., help="Template UUID to update."),
    name: str | None = typer.Option(None, "--name", help="New name."),
    system_prompt: str | None = typer.Option(None, "--system-prompt", help="New system prompt."),
    user_prompt: str | None = typer.Option(None, "--user-prompt", help="New user prompt."),
    greeting: str | None = typer.Option(None, "--greeting", help="New greeting message."),
    required_scope_description: str | None = typer.Option(None, "--required-scope-description", help="Scope requirements description."),
    public: bool | None = typer.Option(None, "--public/--private", help="Change visibility."),
) -> None:
    """Update fields on an existing template."""
    from navdoc.exceptions import NavdocError

    payload = {
        "name": name,
        "system_prompt": system_prompt,
        "user_prompt": user_prompt,
        "greeting": greeting,
        "required_scope_description": required_scope_description,
        "is_public": public,
    }

    async def _run():
        return await _make_client().update_template(template_id, payload)

    try:
        result = asyncio.run(_run())
    except (NavdocError, ValueError) as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)

    console.print(f"Updated template: {result.id}")


@template_app.command("delete")
def template_delete_cmd(
    template_id: str = typer.Argument(..., help="Template UUID to delete."),
) -> None:
    """Delete a template."""
    from navdoc.exceptions import NavdocError

    async def _run():
        await _make_client().delete_template(template_id)

    try:
        asyncio.run(_run())
    except (NavdocError, ValueError) as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)

    console.print(f"Deleted template {template_id}")


@app.command("tools")
def tools_cmd() -> None:
    """List available agent tools."""
    from navdoc.exceptions import NavdocError

    async def _run():
        return await _make_client().list_tools()

    try:
        tools = asyncio.run(_run())
    except (NavdocError, ValueError) as e:
        console.print(f"[bold red]Error:[/bold red] {e}")
        raise typer.Exit(1)

    if not tools:
        console.print("[dim]No tools available.[/dim]")
        return

    table = Table(show_header=True, header_style="bold")
    table.add_column("Name")
    table.add_column("Description")
    for t in tools:
        table.add_row(t.name, t.description)
    console.print(table)


def main() -> None:
    app()
