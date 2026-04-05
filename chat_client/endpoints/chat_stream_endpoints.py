import logging
from typing import Any

from starlette.requests import Request
from starlette.responses import StreamingResponse

from chat_client.core import exceptions_validation


async def chat_response_stream(
    request: Request,
    *,
    require_user_id_json,
    parse_json_payload,
    chat_stream_request,
    new_trace_id,
    build_chat_log_context,
    log_chat_event,
    summarize_messages_for_log,
    summarize_last_user_message_for_log,
    get_dialog,
    get_messages,
    build_model_messages_from_dialog_history,
    get_attachments,
    supports_model_images,
    strip_images_from_messages,
    normalize_chat_messages,
    stream_response_fn,
    json_error_from_exception,
    chat_login_redirect_path,
):
    try:
        logged_in = await require_user_id_json(request, message="You must be logged in to use the chat")
        trace_id = new_trace_id()
        payload = await parse_json_payload(request, chat_stream_request)
        payload_messages = [message.model_dump() for message in payload.messages]
        raw_messages = payload_messages
        dialog_id = str(payload.dialog_id).strip()
        available_attachments: list[dict[str, Any]] = []
        log_context = build_chat_log_context(trace_id=trace_id, user_id=logged_in, dialog_id=dialog_id, model=payload.model)
        log_chat_event(
            logging.INFO,
            "chat.request.start",
            request_path=str(request.url.path),
            **summarize_messages_for_log(payload_messages),
            **log_context,
        )
        if dialog_id:
            await get_dialog(logged_in, dialog_id)
            persisted_messages = await get_messages(logged_in, dialog_id)
            raw_messages = build_model_messages_from_dialog_history(persisted_messages)
            log_chat_event(
                logging.INFO,
                "chat.request.loaded_dialog",
                persisted_message_count=len(persisted_messages),
                **summarize_messages_for_log(raw_messages),
                **log_context,
            )
        attachment_ids: list[int] = []
        seen_attachment_ids: set[int] = set()
        for candidate in raw_messages:
            if not isinstance(candidate, dict):
                continue
            if str(candidate.get("role", "")).strip() != "user":
                continue
            attachments = candidate.get("attachments", [])
            if not isinstance(attachments, list) or not attachments:
                continue
            for attachment in attachments:
                if not isinstance(attachment, dict):
                    continue
                attachment_id = attachment.get("attachment_id")
                if not isinstance(attachment_id, (str, int)):
                    continue
                try:
                    normalized_attachment_id = int(attachment_id)
                except (TypeError, ValueError):
                    continue
                if normalized_attachment_id in seen_attachment_ids:
                    continue
                seen_attachment_ids.add(normalized_attachment_id)
                attachment_ids.append(normalized_attachment_id)
        if attachment_ids:
            available_attachments = await get_attachments(logged_in, attachment_ids)
        if not supports_model_images(payload.model):
            raw_messages = strip_images_from_messages(raw_messages)
            log_chat_event(
                logging.DEBUG,
                "chat.request.images_stripped",
                **summarize_messages_for_log(raw_messages),
                **log_context,
            )
        messages = normalize_chat_messages(raw_messages)
        log_chat_event(
            logging.INFO,
            "chat.request.normalized",
            **summarize_messages_for_log(messages),
            **summarize_last_user_message_for_log(messages),
            **log_context,
        )
        return StreamingResponse(
            stream_response_fn(
                request,
                messages,
                payload.model,
                logged_in,
                dialog_id,
                trace_id,
                available_attachments=available_attachments,
            ),
            media_type="text/event-stream",
        )
    except exceptions_validation.JSONError as error:
        if error.status_code == 401:
            try:
                await request.json()
            except Exception:
                pass
            return json_error_from_exception(error, redirect_to=chat_login_redirect_path(request))
        return json_error_from_exception(error)
