#!/bin/sh
set -e

CHECK_PATHS="chat_client tests bin"

echo "Running ruff format ..."
ruff format $CHECK_PATHS --check

echo "Running mypy ..."
mypy  --config-file pyproject.toml chat_client 

echo "Running ruff check ..."
ruff check $CHECK_PATHS

echo "Running pytest ..."
pytest -q \
  tests/test_chat_service.py \
  tests/test_mcp_client.py \
  tests/test_python_tool.py \
  tests/test_chat_endpoints.py \
  tests/test_user_endpoints.py \
  tests/test_prompt_endpoints.py \
  tests/test_error_endpoints.py
