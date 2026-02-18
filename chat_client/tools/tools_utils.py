import logging
from logging import Logger
import data.config as config


logger: Logger = logging.getLogger(__name__)
tools_available = getattr(config, "TOOLS_AVAILABLE", [])
tools_models = getattr(config, "MCP_MODELS", [])


def is_tools_supported(model: str):

    # Check if tools are available in config
    if not tools_available:
        return False

    # Check if model is in tools models
    if model in tools_models:
        return True

    return False


def is_tool_part(part_dict: dict):
    """
    Check if response part contains tool calls
    """

    if not tools_available:
        return False

    if "tool_calls" in part_dict["message"] and part_dict["message"]["tool_calls"]:
        return True


def call_tools(tools_called: list):
    """
    Call the tools defined in the response parts
    reponse is in the same format as response parts from ollama
    """
    for tool in tools_called:
        try:
            logger.debug(f"Calling tool: {tool}")
            tool_definition = tool["function"]
            function_name = tool_definition["name"]
            arguments = tool_definition["arguments"]
            function = getattr(config, function_name, None)

            if function:
                result = function(**arguments)

                response = {
                    "message": {"content": f"{result}"},
                    "done": True,
                }

                return response
            else:
                logger.error(f"Tool not found: {function_name}")
                response = {
                    "message": {"content": f"Tool not found: {function_name}"},
                    "error": False,
                    "done": True,
                }
                return response

        except Exception as e:
            logger.exception(f"Tool call failed: {e}")
            response = {
                "message": {"content": f"Tool call failed for function: {function_name}"},
                "error": False,
                "done": True,
            }
            return response
