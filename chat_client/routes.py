from starlette.routing import BaseRoute, Mount, Route

from chat_client.endpoints import chat_endpoints
from chat_client.endpoints import error_endpoints
from chat_client.endpoints import prompt_endpoints
from chat_client.endpoints import user_auth_endpoints, user_dialog_endpoints, user_profile_endpoints

user_routes: list[Route] = [
    Route("/user/captcha", user_auth_endpoints.get_captcha, methods=["GET"]),
    Route("/user/signup", user_auth_endpoints.signup_page, methods=["GET"]),
    Route("/user/signup", user_auth_endpoints.signup, methods=["POST"]),
    Route("/user/login", user_auth_endpoints.login_page, methods=["GET"]),
    Route("/user/login", user_auth_endpoints.login, methods=["POST"]),
    Route("/user/verify", user_auth_endpoints.verify_page, methods=["GET"]),
    Route("/user/verify", user_auth_endpoints.verify, methods=["POST"]),
    Route("/user/logout", user_auth_endpoints.logout_page, methods=["GET"]),
    Route("/user/password/reset", user_auth_endpoints.reset_password_page, methods=["GET"]),
    Route("/user/password/reset", user_auth_endpoints.reset_password, methods=["POST"]),
    Route("/user/password/new", user_auth_endpoints.new_password_page, methods=["GET"]),
    Route("/user/password/new", user_auth_endpoints.new_password, methods=["POST"]),
    Route("/user/dialogs", user_dialog_endpoints.dialogs_page, methods=["GET"]),
    Route("/api/user/dialogs", user_dialog_endpoints.list_dialogs, methods=["GET"]),
    Route("/user/profile", user_profile_endpoints.profile_page, methods=["GET"]),
    Route("/api/user/profile", user_profile_endpoints.update_profile, methods=["POST"]),
]

chat_routes: list[Route] = [
    Route("/", chat_endpoints.chat_page, methods=["GET"]),
    Route("/chat", chat_endpoints.stream_chat, methods=["POST"]),
    Route("/chat/{dialog_id:str}", chat_endpoints.chat_page, methods=["GET"]),
    Route("/api/chat/attachments", chat_endpoints.upload_attachment, methods=["POST"]),
    Route("/api/chat/attachments/{attachment_id:int}/preview", chat_endpoints.preview_attachment, methods=["GET"]),
    Route("/api/chat/config", chat_endpoints.get_chat_config, methods=["GET"]),
    Route("/api/chat/models", chat_endpoints.list_chat_models, methods=["GET"]),
    Route("/api/chat/dialogs", chat_endpoints.create_dialog, methods=["POST"]),
    Route("/api/chat/dialogs/{dialog_id:str}", chat_endpoints.get_dialog, methods=["GET"]),
    Route("/api/chat/dialogs/{dialog_id:str}/messages", chat_endpoints.list_messages, methods=["GET"]),
    Route("/api/chat/dialogs/{dialog_id:str}/messages", chat_endpoints.create_message, methods=["POST"]),
    Route("/api/chat/dialogs/{dialog_id:str}/title", chat_endpoints.create_dialog_title, methods=["POST"]),
    Route("/api/chat/dialogs/{dialog_id:str}/assistant-turn-events", chat_endpoints.create_assistant_turn_events, methods=["POST"]),
    Route("/api/chat/messages/{message_id:int}", chat_endpoints.update_message, methods=["POST"]),
    Route("/api/chat/dialogs/{dialog_id:str}", chat_endpoints.delete_dialog, methods=["POST"]),
]

error_routes: list[Route] = [
    Route("/api/error/log", error_endpoints.create_error_log, methods=["POST"]),
]

prompt_routes: list[Route] = [
    Route("/prompts", prompt_endpoints.prompts_page, methods=["GET"]),
    Route("/prompts/new", prompt_endpoints.create_prompt_page, methods=["GET"]),
    Route("/prompts/{prompt_id:int}", prompt_endpoints.prompt_page, methods=["GET"]),
    Route("/prompts/{prompt_id:int}/edit", prompt_endpoints.edit_prompt_page, methods=["GET"]),
    Route("/api/prompts", prompt_endpoints.list_prompts, methods=["GET"]),
    Route("/api/prompts", prompt_endpoints.create_prompt, methods=["POST"]),
    Route("/api/prompts/{prompt_id:int}", prompt_endpoints.get_prompt, methods=["GET"]),
    Route("/api/prompts/{prompt_id:int}", prompt_endpoints.update_prompt, methods=["POST"]),
    Route("/api/prompts/{prompt_id:int}", prompt_endpoints.delete_prompt, methods=["DELETE"]),
]


def build_routes(static_files) -> list[BaseRoute]:
    routes: list[BaseRoute] = [
        Mount("/static", app=static_files, name="static"),
    ]
    routes.extend(user_routes)
    routes.extend(chat_routes)
    routes.extend(error_routes)
    routes.extend(prompt_routes)
    return routes
