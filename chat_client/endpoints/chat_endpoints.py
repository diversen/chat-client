from starlette.requests import Request
from starlette.routing import Route
from starlette.responses import StreamingResponse, JSONResponse, RedirectResponse

from openai import OpenAI
from openai import OpenAIError
import json
from chat_client.core import base_context
from chat_client.core import flash
import data.config as config
import logging
from chat_client.core import user_session
from chat_client.core.templates import get_templates
from chat_client.repositories import chat_repository, user_repository
from chat_client.core.exceptions import UserValidate

# Logger
logger: logging.Logger = logging.getLogger(__name__)
templates = get_templates()

# Configuration
API_BASE_URL = getattr(config, "API_BASE_URL", "")
API_KEY = getattr(config, "API_KEY", "")

MODELS = getattr(config, "MODELS", {})
PROVIDERS = getattr(config, "PROVIDERS", {})

TOOL_REGISTRY = getattr(config, "TOOL_REGISTRY", {})
TOOLS = getattr(config, "TOOLS", [])
TOOL_MODELS = getattr(config, "TOOL_MODELS", [])


async def chat_page(request: Request):
    """
    The GET chat page
    """
    logged_in = await user_session.is_logged_in(request)
    if not logged_in:
        flash.set_notice(request, "You must be logged in to access the chat")
        return RedirectResponse("/user/login")

    model_names = await _get_model_names()

    context = {
        "chat": True,
        "model_names": model_names,
        "default_model": getattr(config, "DEFAULT_MODEL", ""),
        "request": request,
        "title": "Ollama Chat",
    }

    context = await base_context.get_context(request, context)
    return templates.TemplateResponse("home/chat.html", context)


def _execute_tool(tool_call):
    """
    Execute a tool call
    """
    func_name = tool_call["function"]["name"]
    args = json.loads(tool_call["function"]["arguments"])
    logger.info(f"Executing tool: {func_name}({args})")

    if func_name in TOOL_REGISTRY:
        return TOOL_REGISTRY[func_name](**args)
    else:
        return f"Unknown tool: {func_name}"


async def _chat_response_stream(request: Request, messages, model, logged_in):
    profile = await user_repository.get_profile(logged_in)
    if "system_message" in profile and profile["system_message"]:
        system_message = profile["system_message"]
        logger.debug(f"System message: {system_message}")

        # Note that the system message is prepended to the messages as the first message
        # It is a user message with the role "user" because many models does not support 
        # system messages
        system_message_dict = {
            "role": "user",
            "content": system_message,
        }
        messages.insert(0, system_message_dict)

    try:

        provider = MODELS.get(model, {})
        provider_info = PROVIDERS.get(provider, {})

        client = OpenAI(
            api_key=provider_info.get("api_key"),
            base_url=provider_info.get("base_url"),
        )

        chat_args = {
            "model": model,
            "messages": messages,
            "stream": True,
        }

        if model in TOOL_MODELS:
            chat_args["tools"] = TOOLS

        stream_response = client.chat.completions.create(**chat_args)

        tool_call: dict = {}
        for chunk in stream_response:

            if await request.is_disconnected():
                # This ensures that we reach the finally block
                break

            delta = chunk.choices[0].delta

            # Accumulate tool call
            if delta.tool_calls:
                call = delta.tool_calls[0]
                if not tool_call:
                    tool_call = {
                        "id": call.id,
                        "type": call.type,
                        "function": {"name": "", "arguments": ""},
                    }

                if call.function and call.function.name:
                    tool_call["function"]["name"] += call.function.name
                if call.function and call.function.arguments:
                    tool_call["function"]["arguments"] += call.function.arguments

            # If assistant finishes with a tool call, break
            if chunk.choices[0].finish_reason == "tool_calls":
                break

            model_dict = chunk.model_dump()
            json_chunk = json.dumps(model_dict)
            yield f"data: {json_chunk}\n\n"

        if tool_call:
            result = _execute_tool(tool_call)

            # Append assistant tool call and tool response
            messages.append(
                {"role": "assistant", "tool_calls": [tool_call]},
            )

            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call["id"],
                    "content": result,
                }
            )

            chat_args = {
                "model": model,
                "messages": messages,
                "stream": True,
            }

            tool_response = client.chat.completions.create(**chat_args)

            for chunk in tool_response:

                if await request.is_disconnected():
                    # This ensures that we reach the finally block
                    break

                model_dict = chunk.model_dump()
                json_chunk = json.dumps(model_dict)
                yield f"data: {json_chunk}\n\n"

    except OpenAIError:
        logger.exception("OpenAI error")
        yield json.dumps({"error": "An error occured. Please try again later"})

    except Exception:
        logger.exception("Streaming error")
        yield json.dumps({"error": "Streaming failed"})

    finally:
        logger.info("Closing stream")


async def chat_response_stream(request: Request):
    logged_in = await user_session.is_logged_in(request)
    if not logged_in:
        return JSONResponse({"error": True, "message": "You must be logged in to use the chat"}, status_code=401)

    data = await request.json()
    messages = data["messages"]
    model = data["model"]
    return StreamingResponse(
        _chat_response_stream(request, messages, model, logged_in),
        media_type="text/event-stream",
    )


async def config_(request: Request):
    """
    Get frontend configuration
    """
    config_ = {
        "default_model": getattr(config, "DEFAULT_MODEL", ""),
        "tools_callback": getattr(config, "TOOLS_CALLBACK", {}),
        "use_katex": getattr(config, "USE_KATEX", False),
    }

    return JSONResponse(config_)


async def json_tools(request: Request):
    """
    A tool can call this endpoint using JSON data.
    The server will then call a function
    The JSON data is in the form of which specify the tool to call

    {
        "module": "ollama_serv.tools.python_exec",
        "def": "execute",
    }

    """

    # Get JSON data
    data = await request.json()
    tool = request.path_params["tool"]

    # Get tool definition
    tools_callback = getattr(config, "TOOLS_CALLBACK", {})
    tool_def = tools_callback.get(tool, {})

    if not tool_def:
        return JSONResponse({"tool": tool, "text": "Tool not found"}, status_code=404)

    try:
        # import module and call function
        module = __import__(tool_def["module"], fromlist=[tool_def["def"]])
        function = getattr(module, tool_def["def"])
        ret_data = function(data)
        logger.debug(f"Tool result: {ret_data}")

    except Exception:
        logger.exception(f"Error calling tool {tool}")

    # Better error handling
    return JSONResponse({"tool": tool, "text": ret_data})


async def _get_model_names():

    models = []
    for model_name in MODELS.keys():
        models.append(model_name)

    return models


async def list_models(request: Request):

    model_names = await _get_model_names()
    return JSONResponse({"model_names": model_names})


async def create_dialog(request: Request):
    """
    Save dialog to database
    """
    try:
        dialog_id = await chat_repository.create_dialog(request)
        return JSONResponse({"error": False, "dialog_id": dialog_id, "message": "Dialog saved"})
    except UserValidate as e:
        return JSONResponse({"error": True, "message": str(e)})
    except Exception:
        logger.exception("Error saving dialog")
        return JSONResponse({"error": True, "message": "Error saving dialog"})


async def create_message(request: Request):
    """
    Save message to database
    """
    try:
        message_id = await chat_repository.create_message(request)
        return JSONResponse({"message_id": message_id})
    except UserValidate as e:
        return JSONResponse({"error": True, "message": str(e)})
    except Exception:
        logger.exception("Error saving message")
        return JSONResponse({"error": True, "message": "Error saving message"})


async def get_dialog(request: Request):
    """
    Get dialog from database
    """
    try:
        dialog = await chat_repository.get_dialog(request)
        return JSONResponse(dialog)
    except UserValidate as e:
        return JSONResponse({"error": True, "message": str(e)})
    except Exception:
        logger.exception("Error getting dialog")
        return JSONResponse({"error": True, "message": "Error getting dialog"})


async def get_messages(request: Request):
    """
    Get messages from database
    """
    try:
        messages = await chat_repository.get_messages(request)
        return JSONResponse(messages)
    except UserValidate as e:
        return JSONResponse({"error": True, "message": str(e)})
    except Exception:
        logger.exception("Error getting messages")
        return JSONResponse({"error": True, "message": "Error getting messages"})


async def delete_dialog(request: Request):
    """
    Delete dialog from database
    """
    try:
        await chat_repository.delete_dialog(request)
        return JSONResponse({"error": False})
    except UserValidate as e:
        return JSONResponse({"error": True, "message": str(e)})
    except Exception:
        logger.exception("Error deleting dialog")
        return JSONResponse({"error": True, "message": "Error deleting dialog"})


routes_chat: list = [
    Route("/", chat_page),
    Route("/chat/{dialog_id:str}", chat_page),
    Route("/chat", chat_response_stream, methods=["POST"]),
    Route("/tools/{tool:str}", json_tools, methods=["POST"]),
    Route("/config", config_),
    Route("/list", list_models, methods=["GET"]),
    Route("/chat/create-dialog", create_dialog, methods=["POST"]),
    Route("/chat/create-message/{dialog_id}", create_message, methods=["POST"]),
    Route("/chat/delete-dialog/{dialog_id}", delete_dialog, methods=["POST"]),
    Route("/chat/get-dialog/{dialog_id}", get_dialog, methods=["GET"]),
    Route("/chat/get-messages/{dialog_id}", get_messages, methods=["GET"]),
]
