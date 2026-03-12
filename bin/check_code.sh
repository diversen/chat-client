#!/bin/sh
CHECK_PATHS="chat_client tests bin"

echo "Running black ..."
black --check $CHECK_PATHS --config pyproject.toml --extend-exclude '/chat_client/migrations/'

echo "Running mypy ..."
mypy  --config-file pyproject.toml chat_client 

echo "Running flake8 ..."
flake8 $CHECK_PATHS -j 1 --config .flake8

echo "Running pytest ..."
pytest -q \
  tests/test_chat_service.py \
  tests/test_mcp_client.py \
  tests/test_python_tool.py \
  tests/test_chat_endpoints.py \
  tests/test_user_endpoints.py \
  tests/test_prompt_endpoints.py \
  tests/test_error_endpoints.py
