import subprocess
import tempfile
import types
from pathlib import Path
from unittest.mock import patch

from chat_client.core.attachments import prepare_tool_attachment_mount
from chat_client.tools.python_tool import NO_RESULT_ERROR, python, python_insecure


def test_python_tool_evaluates_expression():
    with patch("chat_client.tools.python_runtime.subprocess.run") as run_mock:
        run_mock.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="3\n", stderr="")
        assert python("1 + 2") == "3"


def test_python_tool_allows_imports():
    with patch("chat_client.tools.python_runtime.subprocess.run") as run_mock:
        run_mock.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="ok\n", stderr="")
        result = python("import os\nprint('ok')")
        assert result == "ok"
        run_mock.assert_called_once()


def test_python_tool_allows_open_calls_with_workspace_mount():
    with patch("chat_client.tools.python_runtime.subprocess.run") as run_mock:
        run_mock.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="ok\n", stderr="")
        result = python("print(open('/mnt/data/notes.txt').read())", attachment_host_dir="/tmp/tool-files")
        assert result == "ok"
        called_args = run_mock.call_args[0][0]
        assert "/tmp/tool-files:/mnt/input:ro" in called_args
        assert "/mnt/data:rw,size=65m" in called_args


def test_python_tool_allows_numpy_import():
    with patch("chat_client.tools.python_runtime.subprocess.run") as run_mock:
        run_mock.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="3\n", stderr="")
        result = python("import numpy as np\nprint(np.array([1, 2, 3]).size)")
        assert result == "3"
        run_mock.assert_called_once()


def test_python_tool_invokes_docker_with_hardening_flags():
    with patch("chat_client.tools.python_runtime.subprocess.run") as run_mock:
        run_mock.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="OK\n", stderr="")
        result = python("x = 42", docker_image="secure-python-science")

        assert result == NO_RESULT_ERROR
        called_args = run_mock.call_args[0][0]
        assert called_args[0] == "docker"
        assert "--network" in called_args
        assert "none" in called_args
        assert "--read-only" in called_args
        assert "--cap-drop=ALL" in called_args
        assert "--security-opt" in called_args
        assert "no-new-privileges" in called_args
        assert "secure-python-science" in called_args


def test_python_tool_mounts_attachment_directory_when_present():
    with patch("chat_client.tools.python_runtime.subprocess.run") as run_mock:
        run_mock.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="ok\n", stderr="")
        result = python("print('ok')", attachment_host_dir="/tmp/tool-files")

        assert result == "ok"
        called_args = run_mock.call_args[0][0]
        assert "/tmp/tool-files:/mnt/input:ro" in called_args
        assert "/mnt/data:rw,size=65m" in called_args


def test_python_tool_mounts_empty_directory_when_not_provided():
    with patch("chat_client.tools.python_runtime.subprocess.run") as run_mock:
        run_mock.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="ok\n", stderr="")
        result = python("print('ok')")

        assert result == "ok"
        called_args = run_mock.call_args[0][0]
        source_mount_arg = next(arg for arg in called_args if isinstance(arg, str) and arg.endswith(":/mnt/input:ro"))
        assert source_mount_arg.endswith(":/mnt/input:ro")
        assert "/mnt/data:rw,size=65m" in called_args


def test_prepare_tool_attachment_mount_makes_staged_file_world_readable():
    with tempfile.TemporaryDirectory() as temp_dir:
        source_path = Path(temp_dir) / "notes.txt"
        source_path.write_text("hello", encoding="utf-8")
        source_path.chmod(0o600)

        with prepare_tool_attachment_mount(
            [
                {
                    "attachment_id": 1,
                    "name": "notes.txt",
                    "storage_path": str(source_path),
                    "content_type": "text/plain",
                    "size_bytes": 5,
                }
            ]
        ) as (mount_dir, mounted_attachments):
            staged_path = Path(str(mount_dir)) / mounted_attachments[0]["name"]
            assert staged_path.read_text(encoding="utf-8") == "hello"
            assert staged_path.stat().st_mode & 0o777 == 0o644


def test_python_tool_empty_output_returns_retry_hint():
    with patch("chat_client.tools.python_runtime.subprocess.run") as run_mock:
        run_mock.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        assert python("x = 42") == NO_RESULT_ERROR


def test_python_tool_times_out_infinite_loop():
    with patch("chat_client.tools.python_runtime.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="docker", timeout=10)):
        result = python("while True:\n    pass")
        assert "Execution timed out" in result


def test_python_tool_invalid_syntax_is_reported_by_runtime():
    with patch("chat_client.tools.python_runtime.subprocess.run") as run_mock:
        run_mock.return_value = subprocess.CompletedProcess(args=[], returncode=1, stdout="", stderr="SyntaxError: invalid syntax\n")
        result = python("if True print('x')")
        assert "SyntaxError" in result


def test_python_tool_rejects_non_string_code():
    assert "code must be a string" in python(123)  # type: ignore[arg-type]


def test_python_insecure_allows_open_calls():
    with patch("chat_client.tools.python_runtime.subprocess.run") as run_mock:
        run_mock.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="ok\n", stderr="")
        result = python_insecure("print(open('/etc/hosts').read())")
        assert result == "ok"
        run_mock.assert_called_once()


def test_python_insecure_invokes_docker_without_hardening_flags():
    with patch("chat_client.tools.python_runtime.subprocess.run") as run_mock:
        run_mock.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="OK\n", stderr="")
        result = python_insecure("x = 42", docker_image="secure-python-science")

        assert result == NO_RESULT_ERROR
        called_args = run_mock.call_args[0][0]
        assert called_args[0] == "docker"
        assert "--init" in called_args
        assert "--rm" in called_args
        assert "--network" not in called_args
        assert "--read-only" not in called_args
        assert "--cap-drop=ALL" not in called_args
        assert "--security-opt" not in called_args
        assert "secure-python-science" in called_args


def test_python_tool_uses_configured_timeout():
    config_module = types.SimpleNamespace(PYTHON_TOOL_TIMEOUT_SECONDS=30)
    with patch.dict("sys.modules", {"data.config": config_module}):
        with patch("chat_client.tools.python_runtime.subprocess.run") as run_mock:
            run_mock.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="3\n", stderr="")
            result = python("1 + 2")
            assert result == "3"
            assert run_mock.call_args.kwargs["timeout"] == 30.0


def test_python_tool_zero_timeout_means_infinite():
    config_module = types.SimpleNamespace(PYTHON_TOOL_TIMEOUT_SECONDS=0)
    with patch.dict("sys.modules", {"data.config": config_module}):
        with patch("chat_client.tools.python_runtime.subprocess.run") as run_mock:
            run_mock.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="3\n", stderr="")
            result = python("1 + 2")
            assert result == "3"
            assert run_mock.call_args.kwargs["timeout"] is None
