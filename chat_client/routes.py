from starlette.routing import BaseRoute, Mount, Route

from chat_client.endpoints import chat_endpoints
from chat_client.endpoints import error_endpoints
from chat_client.endpoints import prompt_endpoints
from chat_client.endpoints import user_endpoints

user_routes: list[Route] = [
    Route("/captcha", user_endpoints.captcha_, methods=["GET"]),
    Route("/user/signup", user_endpoints.signup_get, methods=["GET"]),
    Route("/user/signup", user_endpoints.signup_post, methods=["POST"]),
    Route("/user/login", user_endpoints.login_get, methods=["GET"]),
    Route("/user/login", user_endpoints.login_post, methods=["POST"]),
    Route("/user/verify", user_endpoints.verify_get, methods=["GET"]),
    Route("/user/verify", user_endpoints.verify_post, methods=["POST"]),
    Route("/user/logout", user_endpoints.logout_get, methods=["GET"]),
    Route("/user/reset", user_endpoints.reset_password_get, methods=["GET"]),
    Route("/user/reset", user_endpoints.reset_password_post, methods=["POST"]),
    Route("/user/new-password", user_endpoints.new_password_get, methods=["GET"]),
    Route("/user/new-password", user_endpoints.new_password_post, methods=["POST"]),
    Route("/user/dialogs", user_endpoints.list_dialogs, methods=["GET"]),
    Route("/user/dialogs/json", user_endpoints.list_dialogs_json, methods=["GET"]),
    Route("/user/profile", user_endpoints.profile, methods=["GET"]),
    Route("/user/profile", user_endpoints.profile_post, methods=["POST"]),
    Route("/user/is-logged-in", user_endpoints.is_logged_in, methods=["GET"]),
]

chat_routes: list[Route] = [
    Route("/", chat_endpoints.chat_page),
    Route("/chat/{dialog_id:str}", chat_endpoints.chat_page),
    Route("/chat", chat_endpoints.chat_response_stream, methods=["POST"]),
    Route("/config", chat_endpoints.config_),
    Route("/list", chat_endpoints.list_models, methods=["GET"]),
    Route("/chat/create-dialog", chat_endpoints.create_dialog, methods=["POST"]),
    Route("/chat/create-message/{dialog_id}", chat_endpoints.create_message, methods=["POST"]),
    Route("/chat/update-message/{message_id}", chat_endpoints.update_message, methods=["POST"]),
    Route("/chat/delete-dialog/{dialog_id}", chat_endpoints.delete_dialog, methods=["POST"]),
    Route("/chat/get-dialog/{dialog_id}", chat_endpoints.get_dialog, methods=["GET"]),
    Route("/chat/get-messages/{dialog_id}", chat_endpoints.get_messages, methods=["GET"]),
]

error_routes: list[Route] = [
    Route("/error/log", error_endpoints.error_log_post, methods=["POST"]),
]

prompt_routes: list[Route] = [
    Route("/prompt", prompt_endpoints.prompt_list_get, methods=["GET"]),
    Route("/prompt/json", prompt_endpoints.prompt_list_json, methods=["GET"]),
    Route("/prompt/create", prompt_endpoints.prompt_create_get, methods=["GET"]),
    Route("/prompt/create", prompt_endpoints.prompt_create_post, methods=["POST"]),
    Route("/prompt/{prompt_id:int}", prompt_endpoints.prompt_detail, methods=["GET"]),
    Route("/prompt/{prompt_id:int}/edit", prompt_endpoints.prompt_edit_get, methods=["GET"]),
    Route("/prompt/{prompt_id:int}/edit", prompt_endpoints.prompt_edit_post, methods=["POST"]),
    Route("/prompt/{prompt_id:int}/delete", prompt_endpoints.prompt_delete_post, methods=["POST"]),
    Route("/prompt/{prompt_id:int}/json", prompt_endpoints.prompt_detail_json, methods=["GET"]),
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
