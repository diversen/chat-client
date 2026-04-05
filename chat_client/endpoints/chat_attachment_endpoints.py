import logging
from html import escape
from pathlib import Path
from typing import Protocol, cast

from starlette.requests import Request
from starlette.responses import FileResponse, PlainTextResponse

MAX_DIALOG_ATTACHMENTS = 10


class UploadWithRead(Protocol):
    filename: str | None
    content_type: str | None

    async def read(self) -> bytes:
        raise NotImplementedError


async def upload_attachment(
    request: Request,
    *,
    require_user_id_json,
    get_dialog,
    attachment_service,
    attachment_repository,
    exceptions_validation,
    json_success,
    json_error,
    logger: logging.Logger,
):
    try:
        user_id = await require_user_id_json(request, message="You must be logged in to upload files")
        form = await request.form()
        dialog_id = str(form.get("dialog_id", "") or "").strip()
        pending_attachment_ids = form.getlist("pending_attachment_ids")
        normalized_pending_attachment_ids: list[int] = []
        for attachment_id in pending_attachment_ids:
            try:
                normalized_pending_attachment_ids.append(int(attachment_id))
            except (TypeError, ValueError):
                continue

        dialog_attachment_ids: list[int] = []
        if dialog_id:
            await get_dialog(user_id, dialog_id)
            dialog_attachment_ids = await attachment_repository.get_dialog_attachment_ids(user_id, dialog_id)
        pending_attachments = await attachment_repository.get_attachments(user_id, normalized_pending_attachment_ids)
        current_attachment_ids = {
            int(attachment_id)
            for attachment_id in dialog_attachment_ids
            if isinstance(attachment_id, int)
        }
        current_attachment_ids.update(
            int(attachment.get("attachment_id", 0))
            for attachment in pending_attachments
            if int(attachment.get("attachment_id", 0)) > 0
        )
        if len(current_attachment_ids) >= MAX_DIALOG_ATTACHMENTS:
            raise exceptions_validation.UserValidate(
                f"You can attach at most {MAX_DIALOG_ATTACHMENTS} files in a single conversation."
            )

        raw_upload = form.get("file")
        if raw_upload is None or not hasattr(raw_upload, "filename") or not hasattr(raw_upload, "read"):
            raise exceptions_validation.UserValidate("A file upload is required.")
        upload = cast(UploadWithRead, raw_upload)

        filename = str(getattr(upload, "filename", "") or "").strip()
        content_type = str(getattr(upload, "content_type", "") or "").strip().lower()
        file_bytes = await upload.read()
        size_bytes = len(file_bytes)
        safe_name, normalized_content_type = attachment_service.validate_attachment_metadata(
            filename,
            content_type,
            size_bytes,
        )
        attachment_id = await attachment_repository.create_attachment(
            user_id=user_id,
            name=safe_name,
            content_type=normalized_content_type or content_type,
            size_bytes=size_bytes,
            storage_path="",
        )
        if not attachment_id:
            raise RuntimeError("Failed to create attachment id")

        storage_path = attachment_service.build_attachment_storage_path(attachment_id, safe_name)
        storage_path.parent.mkdir(parents=True, exist_ok=True)
        storage_path.write_bytes(file_bytes)
        await attachment_repository.update_attachment_storage_path(user_id, int(attachment_id), str(storage_path))
        attachment = await attachment_repository.get_attachment(user_id, int(attachment_id))
        return json_success(**attachment_service.serialize_attachment_response(attachment))
    except attachment_service.AttachmentValidationError as e:
        return json_error(str(e), status_code=400)
    except exceptions_validation.JSONError:
        raise
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=400)
    except Exception:
        logger.exception("Error uploading attachment")
        return json_error("Error uploading attachment", status_code=500)


async def preview_attachment(
    request: Request,
    *,
    get_user_id_or_redirect,
    attachment_repository,
    exceptions_validation,
    json_error,
    attachment_preview_is_image,
    attachment_preview_is_text,
    logger: logging.Logger,
):
    try:
        user_id_or_response = await get_user_id_or_redirect(
            request,
            notice="You must be logged in to preview attachments",
        )
        if not isinstance(user_id_or_response, int):
            return user_id_or_response

        attachment_id = int(request.path_params.get("attachment_id", 0))
        attachment = await attachment_repository.get_attachment(user_id_or_response, attachment_id)
        storage_path = Path(str(attachment.get("storage_path", "") or "")).expanduser()
        if not storage_path.is_file():
            return json_error("Attachment file was not found on disk.", status_code=404)

        filename = str(attachment.get("name", "") or storage_path.name)
        content_type = str(attachment.get("content_type", "") or "").strip().lower()
        suffix = storage_path.suffix.lower()

        if attachment_preview_is_image(content_type, suffix):
            response = FileResponse(str(storage_path), media_type=content_type or None, filename=filename)
            response.headers["Content-Disposition"] = f'inline; filename="{escape(filename, quote=True)}"'
            return response

        if attachment_preview_is_text(content_type, suffix):
            text_content = storage_path.read_text(encoding="utf-8", errors="replace")
            return PlainTextResponse(text_content, media_type="text/plain")

        response = FileResponse(
            str(storage_path),
            media_type=content_type or "application/octet-stream",
            filename=filename,
        )
        response.headers["Content-Disposition"] = f'attachment; filename="{escape(filename, quote=True)}"'
        return response
    except exceptions_validation.UserValidate as e:
        return json_error(str(e), status_code=404)
    except ValueError:
        return json_error("Attachment id is invalid.", status_code=400)
    except Exception:
        logger.exception("Error previewing attachment")
        return json_error("Error previewing attachment", status_code=500)
