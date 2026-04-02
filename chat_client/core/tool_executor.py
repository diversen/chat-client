import inspect
import logging
from typing import Any, Callable

from chat_client.core import attachments as attachment_service
from chat_client.core import chat_service
from chat_client.core import mcp_client
from chat_client.core.tool_config import LocalToolSpec, normalize_local_tool_specs
from chat_client.tools.python_runtime import PythonRuntimeError


def normalize_local_tool_definition(
    tool_definition: dict[str, Any],
    tool_registry: dict[str, Callable[..., Any]],
) -> dict[str, Any] | None:
    spec = find_local_tool_spec(
        str(tool_definition.get("name", "")).strip(),
        normalize_local_tool_specs(
            tool_registry=tool_registry,
            local_tool_definitions=[tool_definition],
        ),
    )
    if spec is None or not spec.is_executable:
        return None
    return spec.to_openai_tool()


def get_local_tool_definition(
    name: str,
    *,
    tool_registry: dict[str, Callable[..., Any]],
    local_tool_definitions: list[dict[str, Any]] | Any,
) -> dict[str, Any] | None:
    spec = find_local_tool_spec(
        name,
        normalize_local_tool_specs(
            tool_registry=tool_registry,
            local_tool_definitions=local_tool_definitions,
        ),
    )
    if spec is None:
        return None
    return spec.to_openai_tool()


def get_local_tool_specs(
    *,
    tool_registry: dict[str, Callable[..., Any]],
    local_tool_definitions: list[dict[str, Any]] | Any,
) -> list[LocalToolSpec]:
    return normalize_local_tool_specs(
        tool_registry=tool_registry,
        local_tool_definitions=local_tool_definitions,
    )


def find_local_tool_spec(
    name: str,
    local_tool_specs: list[LocalToolSpec],
) -> LocalToolSpec | None:
    if not isinstance(name, str) or not name.strip():
        return None
    for spec in local_tool_specs:
        if spec.name == name:
            return spec
    return None


def list_local_tools(
    *,
    tool_registry: dict[str, Callable[..., Any]],
    local_tool_definitions: list[dict[str, Any]] | Any,
) -> list[dict[str, Any]]:
    return [
        spec.to_openai_tool()
        for spec in get_local_tool_specs(
            tool_registry=tool_registry,
            local_tool_definitions=local_tool_definitions,
        )
        if spec.is_executable
    ]


def find_tool_definition(name: str, tools: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not isinstance(name, str) or not name.strip():
        return None
    for tool in tools:
        if not isinstance(tool, dict):
            continue
        function = tool.get("function", {})
        if not isinstance(function, dict):
            continue
        if function.get("name") == name:
            return tool
    return None


def get_local_tool_execution_options(
    name: str,
    *,
    tool_registry: dict[str, Callable[..., Any]],
    local_tool_definitions: list[dict[str, Any]] | Any,
) -> dict[str, Any]:
    spec = find_local_tool_spec(
        name,
        get_local_tool_specs(
            tool_registry=tool_registry,
            local_tool_definitions=local_tool_definitions,
        ),
    )
    if spec is None or spec.execution.mount_workspace is None:
        return {}
    return {"mount_workspace": spec.execution.mount_workspace}


def local_tool_accepts_attachment_workspace(name: str, tool_registry: dict[str, Callable[..., Any]]) -> bool:
    tool = tool_registry.get(name)
    if not callable(tool):
        return False
    try:
        signature = inspect.signature(tool)
    except (TypeError, ValueError):
        return False
    return "attachment_host_dir" in signature.parameters


def tool_uses_workspace_mount(
    name: str,
    *,
    tool_registry: dict[str, Callable[..., Any]],
    local_tool_definitions: list[dict[str, Any]] | Any,
) -> bool:
    spec = find_local_tool_spec(
        name,
        get_local_tool_specs(
            tool_registry=tool_registry,
            local_tool_definitions=local_tool_definitions,
        ),
    )
    if spec is not None and spec.execution.mount_workspace is not None:
        return bool(spec.execution.mount_workspace)
    return local_tool_accepts_attachment_workspace(name, tool_registry)


def execute_tool(
    tool_call: dict[str, Any],
    *,
    logger: logging.Logger,
    tools: list[dict[str, Any]],
    tool_registry: dict[str, Callable[..., Any]],
    local_tool_definitions: list[dict[str, Any]] | Any,
    has_local_tool_registry: bool,
    has_mcp_config: bool,
    mcp_server_url: str,
    mcp_auth_token: str,
    mcp_timeout_seconds: float,
    log_context: dict[str, Any] | None = None,
    argument_overrides: dict[str, Any] | None = None,
) -> Any:
    func_name = str(tool_call.get("function", {}).get("name", "")).strip()
    if not func_name:
        raise chat_service.ToolArgumentsError("Tool call is missing function name.")

    if not has_local_tool_registry and not has_mcp_config:
        raise chat_service.ToolNotConfiguredError(f'No tool backend is configured for tool "{func_name}".')

    tool_definition = find_tool_definition(func_name, tools)
    if tool_definition is None:
        raise chat_service.ToolNotFoundError(f'Tool "{func_name}" does not exist.')

    function = tool_definition.get("function", {})
    parameters = function.get("parameters", {}) if isinstance(function, dict) else {}
    args = chat_service.parse_tool_arguments(tool_call, logger)
    if isinstance(parameters, dict):
        chat_service.validate_tool_arguments(args, parameters, func_name)
    call_args = dict(args)
    if isinstance(argument_overrides, dict):
        call_args.update(argument_overrides)

    if has_local_tool_registry and func_name in tool_registry:
        logger.info(
            "%s: %s",
            "chat.tool.local.start",
            {
                "tool_name": func_name,
                "arguments_preview": chat_service.summarize_tool_call_for_log(tool_call)["arguments_preview"],
                **(log_context or {}),
            },
        )
        try:
            return tool_registry[func_name](**call_args)
        except TypeError as error:
            raise chat_service.ToolArgumentsError(
                f'Tool "{func_name}" was called with invalid arguments: {error}'
            ) from error
        except chat_service.ToolExecutionError:
            raise
        except PythonRuntimeError as error:
            raise chat_service.ToolBackendError(f'Tool "{func_name}" failed: {error}') from error
        except Exception as error:
            raise chat_service.ToolBackendError(f'Tool "{func_name}" failed: {error}') from error

    if has_mcp_config:
        logger.info(
            "%s: %s",
            "chat.tool.mcp.start",
            {
                "tool_name": func_name,
                "arguments_preview": chat_service.summarize_tool_call_for_log(tool_call)["arguments_preview"],
                **(log_context or {}),
            },
        )
        try:
            return mcp_client.call_tool(
                server_url=mcp_server_url,
                auth_token=mcp_auth_token,
                timeout_seconds=mcp_timeout_seconds,
                name=func_name,
                arguments=args,
            )
        except mcp_client.MCPClientError as error:
            raise chat_service.ToolBackendError(f'MCP tool "{func_name}" failed: {error}') from error

    raise chat_service.ToolNotConfiguredError(f'No tool backend is configured for tool "{func_name}".')


def execute_local_tool_with_runtime_context(
    tool_call: dict[str, Any],
    *,
    logger: logging.Logger,
    tools: list[dict[str, Any]],
    tool_registry: dict[str, Callable[..., Any]],
    local_tool_definitions: list[dict[str, Any]] | Any,
    has_local_tool_registry: bool,
    has_mcp_config: bool,
    mcp_server_url: str,
    mcp_auth_token: str,
    mcp_timeout_seconds: float,
    log_context: dict[str, Any] | None = None,
    available_attachments: list[dict[str, Any]] | None = None,
):
    func_name = str(tool_call.get("function", {}).get("name", "")).strip()
    if tool_uses_workspace_mount(
        func_name,
        tool_registry=tool_registry,
        local_tool_definitions=local_tool_definitions,
    ):
        with attachment_service.prepare_tool_attachment_mount(available_attachments or []) as (attachment_host_dir, _mounted_attachments):
            return execute_tool(
                tool_call,
                logger=logger,
                tools=tools,
                tool_registry=tool_registry,
                local_tool_definitions=local_tool_definitions,
                has_local_tool_registry=has_local_tool_registry,
                has_mcp_config=has_mcp_config,
                mcp_server_url=mcp_server_url,
                mcp_auth_token=mcp_auth_token,
                mcp_timeout_seconds=mcp_timeout_seconds,
                log_context=log_context,
                argument_overrides={"attachment_host_dir": attachment_host_dir},
            )

    return execute_tool(
        tool_call,
        logger=logger,
        tools=tools,
        tool_registry=tool_registry,
        local_tool_definitions=local_tool_definitions,
        has_local_tool_registry=has_local_tool_registry,
        has_mcp_config=has_mcp_config,
        mcp_server_url=mcp_server_url,
        mcp_auth_token=mcp_auth_token,
        mcp_timeout_seconds=mcp_timeout_seconds,
        log_context=log_context,
    )
