import importlib
import os
import subprocess
import tempfile
import uuid
from contextlib import nullcontext

from chat_client.core.attachments import resolve_tool_mount_dir

MAX_CODE_LENGTH = 8_000
DEFAULT_PYTHON_TOOL_TIMEOUT_SECONDS = 10.0
PYTHON_TOOL_DOCKER_IMAGE = "chat-client-python-tool"
NO_RESULT_ERROR = "[stderr]\nNo result produced. Please print the answer or end with an expression."
ATTACHMENT_SOURCE_MOUNT_DIR = "/mnt/input"
ATTACHMENT_TMPFS_SPEC = "rw,size=65m"


class PythonRuntimeError(RuntimeError):
    """
    Raised when the Docker-backed Python runtime cannot be started.
    """


def build_container_name() -> str:
    return f"chat-client-python-tool-{uuid.uuid4().hex[:12]}"


def force_remove_container(container_name: str) -> None:
    try:
        subprocess.run(
            ["docker", "rm", "-f", container_name],
            text=True,
            capture_output=True,
            check=False,
        )
    except Exception:
        pass


def build_runtime_prelude() -> str:
    workspace_dir = resolve_tool_mount_dir()
    return f"""
import os as _chat_client_os
import shutil as _chat_client_shutil
from pathlib import Path as _chat_client_Path

_CHAT_CLIENT_WORKSPACE_ROOT = _chat_client_Path({workspace_dir!r})
_CHAT_CLIENT_SOURCE_ROOT = _chat_client_Path({ATTACHMENT_SOURCE_MOUNT_DIR!r})

def _chat_client_populate_workspace():
    _CHAT_CLIENT_WORKSPACE_ROOT.mkdir(parents=True, exist_ok=True)
    if not _CHAT_CLIENT_SOURCE_ROOT.exists():
        return
    for child in _CHAT_CLIENT_SOURCE_ROOT.iterdir():
        destination = _CHAT_CLIENT_WORKSPACE_ROOT / child.name
        if child.is_dir():
            if destination.exists():
                _chat_client_shutil.rmtree(destination)
            _chat_client_shutil.copytree(child, destination)
            _chat_client_os.chmod(destination, 0o777)
            for nested_path in destination.rglob("*"):
                if nested_path.is_dir():
                    _chat_client_os.chmod(nested_path, 0o777)
                else:
                    _chat_client_os.chmod(nested_path, 0o666)
        else:
            _chat_client_shutil.copy2(child, destination)
            _chat_client_os.chmod(destination, 0o666)

_chat_client_populate_workspace()
""".strip()


def resolve_docker_image(docker_image: str | None) -> str:
    image = str(docker_image or "").strip()
    if image:
        return image
    return PYTHON_TOOL_DOCKER_IMAGE


def resolve_exec_timeout_seconds() -> float | None:
    try:
        config = importlib.import_module("data.config")

        configured = getattr(config, "PYTHON_TOOL_TIMEOUT_SECONDS", DEFAULT_PYTHON_TOOL_TIMEOUT_SECONDS)
        timeout = float(configured)
    except Exception:
        return DEFAULT_PYTHON_TOOL_TIMEOUT_SECONDS

    if timeout < 0:
        return DEFAULT_PYTHON_TOOL_TIMEOUT_SECONDS
    if timeout == 0:
        return None
    return timeout


def validate_code_input(code: str) -> str | None:
    if not isinstance(code, str):
        return "[stderr]\nSecurityError: code must be a string."
    if len(code) > MAX_CODE_LENGTH:
        return f"[stderr]\nSecurityError: code exceeds max length ({MAX_CODE_LENGTH})."
    return None


def _format_docker_runtime_error(stderr_text: str, resolved_docker_image: str) -> str:
    lowered = stderr_text.lower()
    if (
        "unable to find image" in lowered
        or "pull access denied" in lowered
        or "repository does not exist" in lowered
        or "no such image" in lowered
    ):
        return (
            f'Docker image "{resolved_docker_image}" is not available for the Python tool. '
            "Build, load, or configure a valid image before retrying."
        )
    if "cannot connect to the docker daemon" in lowered:
        return "Docker is installed but the daemon is not reachable."
    if "permission denied" in lowered and "docker" in lowered:
        return "Docker is installed but the current process does not have permission to use it."
    if stderr_text.strip():
        return f"Docker failed to start the Python tool container: {stderr_text.strip()}"
    return "Docker failed to start the Python tool container."


def run_python_in_docker(
    code: str,
    docker_image: str | None,
    docker_args: list[str],
    attachment_host_dir: str | None = None,
) -> str:
    container_name = build_container_name()
    try:
        resolved_docker_image = resolve_docker_image(docker_image)
        timeout_seconds = resolve_exec_timeout_seconds()
        temp_attachment_dir_context = tempfile.TemporaryDirectory(prefix="chat-client-python-tool-empty-")
        attachment_dir_context = (
            nullcontext(attachment_host_dir)
            if attachment_host_dir
            else temp_attachment_dir_context
        )
        with attachment_dir_context as resolved_attachment_host_dir:
            if not resolved_attachment_host_dir:
                raise ValueError("attachment_host_dir is required")
            with tempfile.NamedTemporaryFile(mode="w", suffix=".py", encoding="utf-8", delete=False) as code_file:
                wrapped_code = f"{build_runtime_prelude()}\n\n{code}"
                code_file.write(wrapped_code)
                code_file_path = code_file.name
        os.chmod(code_file_path, 0o644)

        docker_command = [
            "docker",
            "run",
            *docker_args,
            "--name",
            container_name,
            "--tmpfs",
            f"{resolve_tool_mount_dir()}:{ATTACHMENT_TMPFS_SPEC}",
            "-v",
            f"{code_file_path}:/sandbox/script.py:ro",
            "-v",
            f"{resolved_attachment_host_dir}:{ATTACHMENT_SOURCE_MOUNT_DIR}:ro",
        ]

        completed = subprocess.run(
            [*docker_command, resolved_docker_image, "/sandbox/script.py"],
            text=True,
            capture_output=True,
            timeout=timeout_seconds,
            check=False,
        )
    except FileNotFoundError:
        raise PythonRuntimeError("Docker is not installed or not available in PATH.")
    except subprocess.TimeoutExpired:
        force_remove_container(container_name)
        if timeout_seconds is None:
            raise PythonRuntimeError("Python tool execution timed out.")
        raise PythonRuntimeError(f"Python tool execution timed out after {timeout_seconds} seconds.")
    finally:
        if "code_file_path" in locals():
            try:
                os.unlink(code_file_path)
            except OSError:
                pass

    if completed.returncode == 125:
        raise PythonRuntimeError(
            _format_docker_runtime_error(completed.stderr or completed.stdout, resolved_docker_image)
        )

    parts: list[str] = []
    stdout_text = completed.stdout.rstrip()
    stderr_text = completed.stderr.rstrip()
    if stdout_text:
        parts.append(stdout_text)
    if stderr_text:
        parts.append(f"[stderr]\n{stderr_text}")

    output = "\n".join(parts).strip()
    if not output or output == "OK":
        return NO_RESULT_ERROR
    return output
