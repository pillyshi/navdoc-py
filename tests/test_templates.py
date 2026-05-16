import json
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from typer.testing import CliRunner

from navdoc.cli import app
from navdoc.models import AgentTemplate, StreamEvent, TemplatePlaceholder

runner = CliRunner()


def make_agent_template(
    template_id="aaaabbbb-cccc-dddd-eeee-ffffaaaabbbb",
    name="My Template",
    description="A test template",
    system_prompt="Be helpful.",
    user_prompt="Tell me about {{topic}}",
    placeholders=None,
    tools=None,
    greeting=None,
    is_public=False,
    star_count=3,
    is_mine=True,
) -> AgentTemplate:
    if placeholders is None:
        placeholders = [TemplatePlaceholder(key="topic", label="Topic", default="Python")]
    return AgentTemplate(
        id=template_id,
        name=name,
        description=description,
        system_prompt=system_prompt,
        user_prompt=user_prompt,
        placeholders=placeholders,
        tools=tools,
        greeting=greeting,
        is_public=is_public,
        star_count=star_count,
        is_starred=False,
        is_mine=is_mine,
    )


def make_crud_client(
    templates: list | None = None,
    created: AgentTemplate | None = None,
    updated: AgentTemplate | None = None,
):
    captured_payloads: dict = {}

    async def _list_templates():
        return templates or []

    async def _create_template(payload: dict):
        captured_payloads["create"] = payload
        return created

    async def _update_template(template_id: str, payload: dict):
        captured_payloads["update"] = {"template_id": template_id, "payload": payload}
        return updated

    async def _delete_template(template_id: str):
        captured_payloads["delete"] = template_id

    client = MagicMock()
    client.list_templates = _list_templates
    client.create_template = _create_template
    client.update_template = _update_template
    client.delete_template = _delete_template
    client._payloads = captured_payloads
    return client


def write_config(tmp_path: Path, data: dict) -> Path:
    config = tmp_path / "config.json"
    config.write_text(json.dumps(data))
    return config


# --- template list ---

def test_template_list_displays_table():
    t = make_agent_template(template_id="aaaabbbb-cccc-dddd-eeee-ffffaaaabbbb", name="My Template", star_count=3, is_mine=True, is_public=False)
    mock_client = make_crud_client(templates=[t])
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["template", "list"])
    assert result.exit_code == 0
    assert "aaaabbbb-cccc-dddd-eeee-ffffaaaabbbb" in result.output
    assert "My Template" in result.output
    assert "3" in result.output


def test_template_list_empty():
    mock_client = make_crud_client(templates=[])
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["template", "list"])
    assert result.exit_code == 0
    assert "No templates found" in result.output


def test_template_list_api_error():
    from navdoc.exceptions import NavdocError

    async def _list_templates():
        raise NavdocError("connection failed")

    mock_client = MagicMock()
    mock_client.list_templates = _list_templates
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["template", "list"])
    assert result.exit_code == 1
    assert "connection failed" in result.output


# --- template create ---

def test_template_create_from_config(tmp_path):
    config = write_config(tmp_path, {
        "name": "My Template",
        "description": "desc",
        "system_prompt": "Be helpful.",
        "user_prompt": "Tell me about {{topic}}",
        "placeholders": [{"key": "topic", "label": "Topic", "default": "Python"}],
    })
    created = make_agent_template()
    mock_client = make_crud_client(created=created)
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["template", "create", str(config)])
    assert result.exit_code == 0
    assert created.id[:8] in result.output or created.id in result.output
    payload = mock_client._payloads["create"]
    assert payload["name"] == "My Template"
    assert payload["system_prompt"] == "Be helpful."
    assert payload["is_public"] is False


def test_template_create_public_flag(tmp_path):
    config = write_config(tmp_path, {"name": "T", "system_prompt": "s", "user_prompt": "q"})
    created = make_agent_template(is_public=True)
    mock_client = make_crud_client(created=created)
    with patch("navdoc.cli._make_client", return_value=mock_client):
        runner.invoke(app, ["template", "create", str(config), "--public"])
    assert mock_client._payloads["create"]["is_public"] is True


def test_template_create_private_flag(tmp_path):
    config = write_config(tmp_path, {"name": "T", "system_prompt": "s", "user_prompt": "q"})
    created = make_agent_template()
    mock_client = make_crud_client(created=created)
    with patch("navdoc.cli._make_client", return_value=mock_client):
        runner.invoke(app, ["template", "create", str(config), "--private"])
    assert mock_client._payloads["create"]["is_public"] is False


def test_template_create_missing_file(tmp_path):
    result = runner.invoke(app, ["template", "create", str(tmp_path / "nonexistent.json")])
    assert result.exit_code == 1
    assert "not found" in result.output


def test_template_create_invalid_json(tmp_path):
    bad = tmp_path / "bad.json"
    bad.write_text("not json")
    result = runner.invoke(app, ["template", "create", str(bad)])
    assert result.exit_code == 1


def test_template_create_api_error(tmp_path):
    from navdoc.exceptions import NavdocError

    config = write_config(tmp_path, {"name": "T", "system_prompt": "s", "user_prompt": "q"})

    async def _create_template(payload):
        raise NavdocError("server error")

    mock_client = MagicMock()
    mock_client.create_template = _create_template
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["template", "create", str(config)])
    assert result.exit_code == 1
    assert "server error" in result.output


# --- template update ---

def test_template_update_name_only():
    updated = make_agent_template(name="New Name")
    mock_client = make_crud_client(updated=updated)
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["template", "update", updated.id, "--name", "New Name"])
    assert result.exit_code == 0
    assert updated.id in result.output
    payload = mock_client._payloads["update"]["payload"]
    assert payload["name"] == "New Name"


def test_template_update_public_flag():
    updated = make_agent_template(is_public=True)
    mock_client = make_crud_client(updated=updated)
    with patch("navdoc.cli._make_client", return_value=mock_client):
        runner.invoke(app, ["template", "update", updated.id, "--public"])
    payload = mock_client._payloads["update"]["payload"]
    assert payload["is_public"] is True


def test_template_update_private_flag():
    updated = make_agent_template(is_public=False)
    mock_client = make_crud_client(updated=updated)
    with patch("navdoc.cli._make_client", return_value=mock_client):
        runner.invoke(app, ["template", "update", updated.id, "--private"])
    payload = mock_client._payloads["update"]["payload"]
    assert payload["is_public"] is False


def test_template_update_greeting():
    updated = make_agent_template(greeting="Hello! How can I help?")
    mock_client = make_crud_client(updated=updated)
    with patch("navdoc.cli._make_client", return_value=mock_client):
        runner.invoke(app, ["template", "update", updated.id, "--greeting", "Hello! How can I help?"])
    payload = mock_client._payloads["update"]["payload"]
    assert payload["greeting"] == "Hello! How can I help?"


def test_template_update_api_error():
    from navdoc.exceptions import NavdocError

    async def _update_template(template_id, payload):
        raise NavdocError("not found")

    mock_client = MagicMock()
    mock_client.update_template = _update_template
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["template", "update", "some-uuid", "--name", "X"])
    assert result.exit_code == 1
    assert "not found" in result.output


# --- template delete ---

def test_template_delete_success():
    mock_client = make_crud_client()
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["template", "delete", "some-uuid"])
    assert result.exit_code == 0
    assert "some-uuid" in result.output
    assert mock_client._payloads["delete"] == "some-uuid"


def test_template_delete_api_error():
    from navdoc.exceptions import NavdocError

    async def _delete_template(template_id):
        raise NavdocError("forbidden")

    mock_client = MagicMock()
    mock_client.delete_template = _delete_template
    with patch("navdoc.cli._make_client", return_value=mock_client):
        result = runner.invoke(app, ["template", "delete", "some-uuid"])
    assert result.exit_code == 1
    assert "forbidden" in result.output
