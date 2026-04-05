import asyncio
import logging

from starlette.requests import Request
from starlette.responses import JSONResponse

MAX_DIALOG_ATTACHMENTS = 10


async def get_chat_config(request: Request, *, config, system_message_denylist, vision_models, build_model_capabilities, json_success):
    config_values = {
        "default_model": getattr(config, "DEFAULT_MODEL", ""),
        "use_katex": getattr(config, "USE_KATEX", False),
        "system_message_denylist": system_message_denylist,
        "vision_models": vision_models,
        "model_capabilities": build_model_capabilities(),
    }
    return json_success(**config_values)


async def list_chat_models(request: Request, *, get_model_names, json_success):
    model_names = await get_model_names()
    return json_success(model_names=model_names)


async def create_dialog(
    request: Request,
    *,
    require_user_id_json,
    parse_json_payload,
    create_dialog_request,
    chat_repository,
    exceptions_validation,
    json_success,
    json_error,
    logger: logging.Logger,
):
    try:
        user_id = await require_user_id_json(request, message="You must be logged in to save a dialog")
        payload = await parse_json_payload(request, create_dialog_request)
        dialog_id = await chat_repository.create_dialog(user_id, payload.title)
        return json_success(dialog_id=dialog_id, message="Dialog saved")
    except exceptions_validation.JSONError:
        raise
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=400)
    except Exception:
        logger.exception("Error saving dialog")
        return json_error("Error saving dialog", status_code=500)


async def create_message(
    request: Request,
    *,
    require_user_id_json,
    parse_json_payload,
    create_message_request,
    attachment_repository,
    chat_repository,
    supports_model_images,
    supports_model_attachments,
    image_modality_error_message: str,
    exceptions_validation,
    json_success,
    json_error,
    logger: logging.Logger,
):
    try:
        user_id = await require_user_id_json(request, message="You must be logged in in order to create a message")
        dialog_id = str(request.path_params.get("dialog_id", "")).strip()
        if not dialog_id:
            raise exceptions_validation.UserValidate("Dialog id is required")

        payload = await parse_json_payload(request, create_message_request)
        if payload.role == "user" and payload.images:
            selected_model = payload.model.strip()
            if not selected_model:
                raise exceptions_validation.UserValidate("Model is required when attaching images")
            if not supports_model_images(selected_model):
                raise exceptions_validation.UserValidate(image_modality_error_message)
        if payload.role == "user" and payload.attachments:
            selected_model = payload.model.strip()
            if not selected_model:
                raise exceptions_validation.UserValidate("Model is required when attaching files")
            if not supports_model_attachments(selected_model):
                raise exceptions_validation.UserValidate("The selected model does not support file attachments.")
        if payload.attachments:
            await attachment_repository.get_attachments(
                user_id,
                [attachment.attachment_id for attachment in payload.attachments],
            )
        dialog_messages = await chat_repository.get_messages(user_id, dialog_id)
        existing_media_count = 0
        for message in dialog_messages:
            if not isinstance(message, dict):
                continue
            images = message.get("images", [])
            attachments = message.get("attachments", [])
            existing_media_count += len(images) if isinstance(images, list) else 0
            existing_media_count += len(attachments) if isinstance(attachments, list) else 0
        new_media_count = len(payload.images) + len(payload.attachments)
        if existing_media_count + new_media_count > MAX_DIALOG_ATTACHMENTS:
            raise exceptions_validation.UserValidate(
                f"You can attach at most {MAX_DIALOG_ATTACHMENTS} images/files in a single conversation."
            )
        message_id = await chat_repository.create_message(
            user_id,
            dialog_id,
            payload.role,
            payload.content,
            [image.model_dump() for image in payload.images],
            [attachment.model_dump() for attachment in payload.attachments],
        )
        return json_success(message_id=message_id)
    except exceptions_validation.JSONError:
        raise
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=400)
    except Exception:
        logger.exception("Error saving message")
        return json_error("Error saving message", status_code=500)


async def create_dialog_title(
    request: Request,
    *,
    require_user_id_json,
    chat_repository,
    dialog_title_model: str,
    is_pending_dialog_title,
    extract_first_user_message,
    create_dialog_title_fn,
    derive_dialog_title_from_user_message,
    log_chat_event,
    exceptions_validation,
    json_success,
    json_error,
    logger: logging.Logger,
):
    dialog_id = ""
    try:
        user_id = await require_user_id_json(request, message="You must be logged in to update a dialog title")
        dialog_id = str(request.path_params.get("dialog_id", "")).strip()
        if not dialog_id:
            raise exceptions_validation.UserValidate("Dialog id is required")

        dialog = await chat_repository.get_dialog(user_id, dialog_id)
        existing_title = str(dialog.get("title", "")).strip()
        if not is_pending_dialog_title(existing_title):
            return json_success(dialog_id=dialog_id, title=existing_title, generated=False)

        messages = await chat_repository.get_messages(user_id, dialog_id)
        first_user_message = extract_first_user_message(messages)
        if not first_user_message:
            return json_success(dialog_id=dialog_id, title=existing_title, generated=False)

        title_source = "derived"
        title_model = ""
        if dialog_title_model:
            title_source = "model"
            title_model = dialog_title_model
            generated_title = await asyncio.to_thread(
                create_dialog_title_fn,
                first_user_message,
                dialog_title_model,
            )
        else:
            generated_title = derive_dialog_title_from_user_message(first_user_message)
        log_chat_event(
            logging.INFO,
            "chat.dialog_title.generated",
            user_id=user_id,
            dialog_id=dialog_id,
            source=title_source,
            model=title_model,
            generated_title=generated_title,
        )
        result = await chat_repository.update_dialog_title(user_id, dialog_id, generated_title)
        return json_success(**result, generated=True)
    except exceptions_validation.JSONError:
        raise
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=400)
    except Exception:
        logger.exception(
            "Error generating dialog title",
            extra={
                "dialog_id": dialog_id,
                "model": dialog_title_model or "",
            },
        )
        return json_error("Error generating dialog title", status_code=500)


async def create_assistant_turn_events(
    request: Request,
    *,
    require_user_id_json,
    parse_json_payload,
    create_assistant_turn_events_request,
    chat_repository,
    exceptions_validation,
    json_success,
    json_error,
    logger: logging.Logger,
):
    try:
        user_id = await require_user_id_json(request, message="You must be logged in in order to create assistant turn events")
        dialog_id = str(request.path_params.get("dialog_id", "")).strip()
        if not dialog_id:
            raise exceptions_validation.UserValidate("Dialog id is required")
        await chat_repository.get_dialog(user_id, dialog_id)
        payload = await parse_json_payload(request, create_assistant_turn_events_request)
        await chat_repository.create_assistant_turn_events(
            user_id=user_id,
            dialog_id=dialog_id,
            turn_id=payload.turn_id,
            events=[event.model_dump() for event in payload.events],
        )
        return json_success()
    except exceptions_validation.JSONError:
        raise
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=400)
    except Exception:
        logger.exception("Error saving assistant turn events")
        return json_error("Error saving assistant turn events", status_code=500)


async def get_dialog(
    request: Request,
    *,
    require_user_id_json,
    chat_repository,
    exceptions_validation,
    json_error,
    logger: logging.Logger,
):
    try:
        user_id = await require_user_id_json(request, message="You must be logged in to get a dialog")
        dialog_id = str(request.path_params.get("dialog_id", "")).strip()
        if not dialog_id:
            raise exceptions_validation.UserValidate("Dialog id is required")
        dialog = await chat_repository.get_dialog(user_id, dialog_id)
        return JSONResponse(dialog)
    except exceptions_validation.JSONError:
        raise
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=400)
    except Exception:
        logger.exception("Error getting dialog")
        return json_error("Error getting dialog", status_code=500)


async def list_messages(
    request: Request,
    *,
    require_user_id_json,
    chat_repository,
    exceptions_validation,
    json_error,
    logger: logging.Logger,
):
    try:
        user_id = await require_user_id_json(request, message="You must be logged in to get a dialog")
        dialog_id = str(request.path_params.get("dialog_id", "")).strip()
        if not dialog_id:
            raise exceptions_validation.UserValidate("Dialog id is required")
        messages = await chat_repository.get_messages(user_id, dialog_id)
        return JSONResponse(messages)
    except exceptions_validation.JSONError:
        raise
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=400)
    except Exception:
        logger.exception("Error getting messages")
        return json_error("Error getting messages", status_code=500)


async def delete_dialog(
    request: Request,
    *,
    require_user_id_json,
    chat_repository,
    exceptions_validation,
    json_success,
    json_error,
    logger: logging.Logger,
):
    try:
        user_id = await require_user_id_json(request, message="You must be logged in to delete a dialog")
        dialog_id = str(request.path_params.get("dialog_id", "")).strip()
        if not dialog_id:
            raise exceptions_validation.UserValidate("Dialog id is required")
        await chat_repository.delete_dialog(user_id, dialog_id)
        return json_success()
    except exceptions_validation.JSONError:
        raise
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=400)
    except Exception:
        logger.exception("Error deleting dialog")
        return json_error("Error deleting dialog", status_code=500)


async def update_message(
    request: Request,
    *,
    require_user_id_json,
    parse_json_payload,
    update_message_request,
    chat_repository,
    exceptions_validation,
    json_success,
    json_error,
    logger: logging.Logger,
):
    try:
        user_id = await require_user_id_json(
            request,
            message="You must be logged in to update a message",
        )
        raw_message_id = request.path_params.get("message_id")
        if raw_message_id is None:
            raise ValueError("Missing message id")
        message_id = int(raw_message_id)
        payload = await parse_json_payload(request, update_message_request)
        result = await chat_repository.update_message(user_id, message_id, payload.content)
        return json_success(**result)
    except exceptions_validation.JSONError:
        raise
    except (TypeError, ValueError):
        return json_error("Invalid message id", status_code=400)
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=400)
    except Exception:
        logger.exception("Error updating message")
        return json_error("Error updating message", status_code=500)
