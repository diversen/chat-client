import logging

import pytest

from chat_client.core import tool_config
from chat_client.core import tool_executor


def test_inferred_tool_schema_hides_internal_parameters_and_warns(caplog):
    def python_tool(code: str, docker_image: str | None = None, attachment_host_dir: str | None = None):
        """Run Python code."""
        return code

    tool_config._warned_inferred_tool_names.clear()
    caplog.set_level(logging.WARNING, logger="chat_client.core.tool_config")

    specs = tool_config.normalize_local_tool_specs(
        tool_registry={"python_tool": python_tool},
        local_tool_definitions=[],
    )

    assert len(specs) == 1
    assert specs[0].description == "Run Python code."
    assert specs[0].input_schema == {
        "type": "object",
        "properties": {"code": {"type": "string"}},
        "additionalProperties": False,
        "required": ["code"],
    }
    assert 'Inferring schema for local tool "python_tool"' in caplog.text


def test_inferred_tool_schema_rejects_unsupported_required_parameter():
    def bad_tool(payload):
        return payload

    tool_config._warned_inferred_tool_names.clear()

    with pytest.raises(ValueError) as error:
        tool_config.normalize_local_tool_specs(
            tool_registry={"bad_tool": bad_tool},
            local_tool_definitions=[],
        )

    assert str(error.value) == (
        'Cannot infer schema for local tool "bad_tool": required parameter "payload" must have a supported type annotation.'
    )


def test_build_startup_tool_summary_lists_executable_local_tools():
    def lookup_wiki(title: str):
        return title

    summary = tool_executor.build_startup_tool_summary(
        tool_registry={"lookup_wiki": lookup_wiki},
        local_tool_definitions=[
            {
                "name": "lookup_wiki",
                "description": "Lookup Wikipedia pages",
                "input_schema": {
                    "type": "object",
                    "properties": {"title": {"type": "string"}},
                    "required": ["title"],
                    "additionalProperties": False,
                },
            }
        ],
        mcp_server_url="",
        mcp_auth_token="",
        tool_models=["qwen3:latest"],
    )

    assert summary == {
        "local_tool_count": 1,
        "local_tools": [{"name": "lookup_wiki", "description": "Lookup Wikipedia pages"}],
        "mcp": {"enabled": False, "server_url": "", "auth_configured": False},
        "tool_models": ["qwen3:latest"],
    }


def test_build_startup_tool_summary_reports_mcp_without_auth_token():
    summary = tool_executor.build_startup_tool_summary(
        tool_registry={},
        local_tool_definitions=[],
        mcp_server_url=" http://127.0.0.1:5000/mcp ",
        mcp_auth_token="secret-token",
        tool_models="not-a-list",
    )

    assert summary == {
        "local_tool_count": 0,
        "local_tools": [],
        "mcp": {
            "enabled": True,
            "server_url": "http://127.0.0.1:5000/mcp",
            "auth_configured": True,
        },
        "tool_models": [],
    }
