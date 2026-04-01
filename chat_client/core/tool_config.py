from dataclasses import dataclass, field
from typing import Any, Callable


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
        specs.append(
            LocalToolSpec(
                name=name,
                callable=tool_callable,
                description=str(getattr(tool_callable, "__doc__", "") or "").strip(),
            )
        )
    return specs
