import re
import shutil
import tempfile
import os
from collections.abc import Iterable
from contextlib import contextmanager
from pathlib import Path
from typing import Any

import data.config as config

DEFAULT_ATTACHMENT_STORAGE_DIRNAME = "attachments"
DEFAULT_MAX_ATTACHMENT_SIZE_BYTES = 10 * 1024 * 1024
DEFAULT_TOOL_MOUNT_DIR = "/mnt/data"
FILENAME_SAFE_PATTERN = re.compile(r"[^A-Za-z0-9._-]+")

ALLOWED_ATTACHMENT_EXTENSIONS = {
    ".txt",
    ".md",
    ".markdown",
    ".csv",
    ".json",
    ".py",
    ".yaml",
    ".yml",
    ".log",
    ".xml",
    ".html",
    ".htm",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".webp",
}

ALLOWED_ATTACHMENT_CONTENT_TYPES = {
    "text/plain",
    "text/markdown",
    "text/csv",
    "application/json",
    "application/x-python-code",
    "text/x-python",
    "application/xml",
    "text/xml",
    "text/html",
    "image/png",
    "image/jpeg",
    "image/gif",
    "image/webp",
}


class AttachmentValidationError(ValueError):
    pass


def resolve_attachment_storage_dir() -> Path:
    configured = getattr(config, "ATTACHMENT_STORAGE_DIR", "")
    if configured:
        path = Path(configured)
    else:
        data_dir = Path(getattr(config, "DATA_DIR", "data"))
        path = data_dir / DEFAULT_ATTACHMENT_STORAGE_DIRNAME
    path.mkdir(parents=True, exist_ok=True)
    return path


def resolve_tool_mount_dir() -> str:
    return str(getattr(config, "PYTHON_TOOL_ATTACHMENT_MOUNT_DIR", DEFAULT_TOOL_MOUNT_DIR)).strip() or DEFAULT_TOOL_MOUNT_DIR


def resolve_max_attachment_size_bytes() -> int:
    configured = getattr(config, "MAX_ATTACHMENT_SIZE_BYTES", DEFAULT_MAX_ATTACHMENT_SIZE_BYTES)
    try:
        resolved = int(configured)
    except (TypeError, ValueError):
        return DEFAULT_MAX_ATTACHMENT_SIZE_BYTES
    if resolved < 1:
        return DEFAULT_MAX_ATTACHMENT_SIZE_BYTES
    return resolved


def sanitize_attachment_filename(filename: str, fallback_stem: str = "attachment") -> str:
    original_name = Path(str(filename or "")).name.strip()
    if not original_name:
        original_name = fallback_stem

    suffix = Path(original_name).suffix.lower()
    stem = Path(original_name).stem or fallback_stem
    normalized_stem = FILENAME_SAFE_PATTERN.sub("_", stem).strip("._") or fallback_stem
    normalized_suffix = FILENAME_SAFE_PATTERN.sub("", suffix).lower()
    return f"{normalized_stem}{normalized_suffix}"


def validate_attachment_metadata(filename: str, content_type: str, size_bytes: int) -> tuple[str, str]:
    safe_name = sanitize_attachment_filename(filename)
    suffix = Path(safe_name).suffix.lower()
    normalized_content_type = str(content_type or "").split(";", 1)[0].strip().lower()
    if suffix not in ALLOWED_ATTACHMENT_EXTENSIONS:
        raise AttachmentValidationError(f"Unsupported attachment type for {safe_name}.")
    if normalized_content_type and normalized_content_type not in ALLOWED_ATTACHMENT_CONTENT_TYPES:
        raise AttachmentValidationError(f"Unsupported attachment content type for {safe_name}.")
    if size_bytes > resolve_max_attachment_size_bytes():
        max_size_mb = resolve_max_attachment_size_bytes() // (1024 * 1024)
        raise AttachmentValidationError(f"{safe_name} is larger than {max_size_mb}MB.")
    return safe_name, normalized_content_type


def build_attachment_storage_path(attachment_id: int, filename: str) -> Path:
    safe_name = sanitize_attachment_filename(filename, fallback_stem=f"attachment_{attachment_id}")
    return resolve_attachment_storage_dir() / f"{attachment_id}_{safe_name}"


def format_attachment_note(attachments: list[dict[str, Any]] | None) -> str:
    if not attachments:
        return ""
    lines = ["Attached files available to tools:"]
    for path in list_attachment_paths(attachments):
        lines.append(f"- {path}")
    if len(lines) == 1:
        return ""
    return "\n".join(lines)


def list_attachment_paths(attachments: list[dict[str, Any]] | None) -> list[str]:
    if not attachments:
        return []
    mount_dir = resolve_tool_mount_dir().rstrip("/")
    paths: list[str] = []
    for attachment in attachments:
        name = sanitize_attachment_filename(str(attachment.get("name", "")) or "attachment")
        paths.append(f"{mount_dir}/{name}")
    return paths


def serialize_attachment_response(attachment: dict[str, Any]) -> dict[str, Any]:
    return {
        "attachment_id": int(attachment.get("attachment_id", 0)),
        "name": str(attachment.get("name", "")),
        "content_type": str(attachment.get("content_type", "")),
        "size_bytes": int(attachment.get("size_bytes", 0)),
    }


def _choose_unique_name(name: str, used_names: set[str]) -> str:
    candidate = sanitize_attachment_filename(name)
    if candidate not in used_names:
        used_names.add(candidate)
        return candidate

    stem = Path(candidate).stem or "attachment"
    suffix = Path(candidate).suffix
    counter = 2
    while True:
        candidate = f"{stem}_{counter}{suffix}"
        if candidate not in used_names:
            used_names.add(candidate)
            return candidate
        counter += 1


@contextmanager
def prepare_tool_attachment_mount(attachments: Iterable[dict[str, Any]]):
    attachment_list = list(attachments)
    used_names: set[str] = set()
    with tempfile.TemporaryDirectory(prefix="chat-client-tool-files-") as temp_dir:
        temp_path = Path(temp_dir)
        os.chmod(temp_path, 0o755)
        mounted_attachments: list[dict[str, Any]] = []

        for attachment in attachment_list:
            source_path = Path(str(attachment.get("storage_path", "")))
            if not source_path.is_file():
                continue

            mounted_name = _choose_unique_name(str(attachment.get("name", "")), used_names)
            destination_path = temp_path / mounted_name
            shutil.copy2(source_path, destination_path)
            os.chmod(destination_path, 0o644)
            mounted_attachments.append(
                {
                    "attachment_id": int(attachment.get("attachment_id", 0)),
                    "name": mounted_name,
                    "original_name": str(attachment.get("name", "")),
                    "content_type": str(attachment.get("content_type", "")),
                    "size_bytes": int(attachment.get("size_bytes", 0)),
                    "path": f"{resolve_tool_mount_dir().rstrip('/')}/{mounted_name}",
                }
            )

        yield str(temp_path), mounted_attachments
