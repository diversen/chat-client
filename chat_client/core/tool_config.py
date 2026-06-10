import logging
from dataclasses import dataclass, field
from inspect import Parameter, signature
from typing import Any, Callable

logger = logging.getLogger(__name__)
INTERNAL_TOOL_PARAMETER_NAMES = {"attachment_host_dir", "docker_image"}
_warned_inferred_tool_names: set[str] = set()


@dataclass(frozen=True)
class LocalToolExecutionOptions:
    mount_workspace: bool | None = None


@dataclass(frozen=True)
class LocalToolSpec:
    name: str
    callable: Callable[..., Any] | None = None
    description: str = ""
    input_schema: dict[str, Any] = field(default_factory=lambda: {"type": "object", "properties": {}})
    execution: LocalToolExecutionOptions = field(default_factory=LocalToolExecutionOptions)

    @property
    def is_executable(self) -> bool:
        return callable(self.callable)

    def to_openai_tool(self) -> dict[str, Any]:
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_schema,
            },
        }


def _normalize_input_schema(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    return {"type": "object", "properties": {}}


def _normalize_execution_options(value: Any) -> LocalToolExecutionOptions:
    if not isinstance(value, dict):
        return LocalToolExecutionOptions()
    mount_workspace = value.get("mount_workspace")
    if isinstance(mount_workspace, bool):
        return LocalToolExecutionOptions(mount_workspace=mount_workspace)
    return LocalToolExecutionOptions()


def _json_type_for_annotation(annotation: Any) -> str | None:
    if annotation is str:
        return "string"
    if annotation is bool:
        return "boolean"
    if annotation is int:
        return "integer"
    if annotation is float:
        return "number"
    if annotation is list:
        return "array"
    if annotation is dict:
        return "object"
    return None


def _schema_from_callable(tool_name: str, tool_callable: Callable[..., Any]) -> dict[str, Any]:
    try:
        tool_signature = signature(tool_callable)
    except (TypeError, ValueError):
        return {"type": "object", "properties": {}}

    properties: dict[str, Any] = {}
    required: list[str] = []
    for name, parameter in tool_signature.parameters.items():
        if name in INTERNAL_TOOL_PARAMETER_NAMES:
            continue
        if parameter.kind not in {Parameter.POSITIONAL_OR_KEYWORD, Parameter.KEYWORD_ONLY}:
            continue

        parameter_schema: dict[str, Any] = {}
        json_type = _json_type_for_annotation(parameter.annotation)
        if json_type is None and parameter.default is Parameter.empty:
            raise ValueError(
                f'Cannot infer schema for local tool "{tool_name}": required parameter "{name}" must have a supported type annotation.'
            )
        if json_type:
            parameter_schema["type"] = json_type
        properties[name] = parameter_schema
        if parameter.default is Parameter.empty:
            required.append(name)

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
        "additionalProperties": False,
    }
    if required:
        schema["required"] = required
    return schema


def normalize_local_tool_specs(
    *,
    tool_registry: dict[str, Callable[..., Any]] | Any,
    local_tool_definitions: list[dict[str, Any]] | Any,
) -> list[LocalToolSpec]:
    normalized_registry = tool_registry if isinstance(tool_registry, dict) else {}

    specs: list[LocalToolSpec] = []
    configured_names: set[str] = set()
    if isinstance(local_tool_definitions, list):
        for definition in local_tool_definitions:
            if not isinstance(definition, dict):
                continue
            name = definition.get("name")
            if not isinstance(name, str) or not name.strip():
                continue
            configured_names.add(name)
            tool_callable = normalized_registry.get(name)
            description = definition.get("description", "")
            specs.append(
                LocalToolSpec(
                    name=name,
                    callable=tool_callable,
                    description=description if isinstance(description, str) else "",
                    input_schema=_normalize_input_schema(definition.get("input_schema")),
                    execution=_normalize_execution_options(definition.get("execution")),
                )
            )
    for name, tool_callable in normalized_registry.items():
        if name in configured_names:
            continue
        if not isinstance(name, str) or not name.strip():
            continue
        if not callable(tool_callable):
            continue
        input_schema = _schema_from_callable(name, tool_callable)
        if name not in _warned_inferred_tool_names:
            logger.warning('Inferring schema for local tool "%s" from callable signature. Define LOCAL_TOOL_DEFINITIONS to override.', name)
            _warned_inferred_tool_names.add(name)
        specs.append(
            LocalToolSpec(
                name=name,
                callable=tool_callable,
                description=str(getattr(tool_callable, "__doc__", "") or "").strip(),
                input_schema=input_schema,
            )
        )
    return specs
