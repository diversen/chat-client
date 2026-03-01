import subprocess
from unittest.mock import patch

from chat_client.tools.python_tool import NO_RESULT_ERROR, python


def test_python_tool_evaluates_expression():
    with patch("chat_client.tools.python_tool.subprocess.run") as run_mock:
        run_mock.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="3\n", stderr="")
        assert python("1 + 2") == "3"


def test_python_tool_allows_imports():
    with patch("chat_client.tools.python_tool.subprocess.run") as run_mock:
        run_mock.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="ok\n", stderr="")
        result = python("import os\nprint('ok')")
        assert result == "ok"
        run_mock.assert_called_once()


def test_python_tool_blocks_open_calls():
    with patch("chat_client.tools.python_tool.subprocess.run") as run_mock:
        result = python("open('/etc/passwd').read()")
        assert "SecurityError" in result
        assert "Call to 'open' is not allowed." in result
        run_mock.assert_not_called()


def test_python_tool_allows_numpy_import():
    with patch("chat_client.tools.python_tool.subprocess.run") as run_mock:
        run_mock.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="3\n", stderr="")
        result = python("import numpy as np\nprint(np.array([1, 2, 3]).size)")
        assert result == "3"
        run_mock.assert_called_once()


def test_python_tool_invokes_docker_with_hardening_flags():
    with patch("chat_client.tools.python_tool.subprocess.run") as run_mock:
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


def test_python_tool_empty_output_returns_retry_hint():
    with patch("chat_client.tools.python_tool.subprocess.run") as run_mock:
        run_mock.return_value = subprocess.CompletedProcess(args=[], returncode=0, stdout="", stderr="")
        assert python("x = 42") == NO_RESULT_ERROR


def test_python_tool_times_out_infinite_loop():
    with patch("chat_client.tools.python_tool.subprocess.run", side_effect=subprocess.TimeoutExpired(cmd="docker", timeout=10)):
        result = python("while True:\n    pass")
        assert "Execution timed out" in result
