import ast
import os
import subprocess
import tempfile
from typing import Any


MAX_CODE_LENGTH = 8_000
EXEC_TIMEOUT_SECONDS = 10.0
DEFAULT_DOCKER_IMAGE = "secure-python"
NO_RESULT_ERROR = "[stderr]\nNo result produced. Please print the answer or end with an expression."


BLOCKED_CALL_NAMES = {
    "__import__",
    "breakpoint",
    "compile",
    "delattr",
    "dir",
    "eval",
    "exec",
    "getattr",
    "globals",
    "hasattr",
    "help",
    "input",
    "locals",
    "open",
    "quit",
    "setattr",
    "vars",
    "exit",
}


class UnsafeCodeError(ValueError):
    pass


class _SecurityValidator(ast.NodeVisitor):
    def visit_Import(self, node: ast.Import) -> Any:
        self.generic_visit(node)

    def visit_ImportFrom(self, node: ast.ImportFrom) -> Any:
        self.generic_visit(node)

    def visit_Attribute(self, node: ast.Attribute) -> Any:
        if node.attr.startswith("__"):
            raise UnsafeCodeError("Dunder attribute access is not allowed.")
        self.generic_visit(node)

    def visit_Name(self, node: ast.Name) -> Any:
        if node.id.startswith("__"):
            raise UnsafeCodeError("Dunder names are not allowed.")
        self.generic_visit(node)

    def visit_Call(self, node: ast.Call) -> Any:
        if isinstance(node.func, ast.Name) and node.func.id in BLOCKED_CALL_NAMES:
            raise UnsafeCodeError(f"Call to '{node.func.id}' is not allowed.")
        if isinstance(node.func, ast.Attribute):
            if node.func.attr in BLOCKED_CALL_NAMES or node.func.attr.startswith("__"):
                raise UnsafeCodeError(f"Call to '{node.func.attr}' is not allowed.")
        self.generic_visit(node)


def _validate_code(code: str) -> None:
    tree = ast.parse(code, mode="exec")
    _SecurityValidator().visit(tree)


def _resolve_docker_image(docker_image: str | None) -> str:
    image = str(docker_image or "").strip()
    if image:
        return image

    try:
        import data.config as config  # type: ignore

        configured = str(getattr(config, "PYTHON_TOOL_DOCKER_IMAGE", "") or "").strip()
        if configured:
            return configured
    except Exception:
        pass

    return DEFAULT_DOCKER_IMAGE


def python(code: str, docker_image: str | None = None) -> str:
    """
    Execute Python code in a hardened Docker container and return output/result.
    """
    if not isinstance(code, str):
        return "[stderr]\nSecurityError: code must be a string."

    if len(code) > MAX_CODE_LENGTH:
        return f"[stderr]\nSecurityError: code exceeds max length ({MAX_CODE_LENGTH})."

    try:
        _validate_code(code)
    except (SyntaxError, UnsafeCodeError) as exc:
        return f"[stderr]\nSecurityError: {exc}"

    try:
        resolved_docker_image = _resolve_docker_image(docker_image)
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", encoding="utf-8", delete=False) as code_file:
            code_file.write(code)
            code_file_path = code_file.name
        os.chmod(code_file_path, 0o644)

        completed = subprocess.run(
            [
                "docker",
                "run",
                "--network",
                "none",
                "--init",
                "--rm",
                "--read-only",
                "--tmpfs",
                "/tmp:rw,noexec,nosuid,size=64m",
                "--cap-drop=ALL",
                "--security-opt",
                "no-new-privileges",
                "--memory=256m",
                "--memory-swap=256m",
                "--cpus=0.5",
                "--pids-limit=128",
                "--ulimit",
                "nproc=128:128",
                "--ulimit",
                "stack=67108864",
                "--user",
                "65534:65534",
                "-v",
                f"{code_file_path}:/sandbox/script.py:ro",
                resolved_docker_image,
                "/sandbox/script.py",
            ],
            text=True,
            capture_output=True,
            timeout=EXEC_TIMEOUT_SECONDS,
            check=False,
        )
    except FileNotFoundError:
        return "[stderr]\nDocker is not installed or not available in PATH."
    except subprocess.TimeoutExpired:
        return f"[stderr]\nExecution timed out after {EXEC_TIMEOUT_SECONDS} seconds."
    finally:
        if "code_file_path" in locals():
            try:
                os.unlink(code_file_path)
            except OSError:
                pass

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
