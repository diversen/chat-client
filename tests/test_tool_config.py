import logging

import pytest

from chat_client.core import tool_config


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
