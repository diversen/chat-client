# AGENTS

## Project

- `chat-client` is a Python 3.10+ Starlette app with server-rendered templates and static JS/CSS.
- App entrypoint: `chat_client/main.py`
- CLI entrypoint: `chat_client/cli.py` via `chat-client`
- Runtime data and config live under `data/`

## Layout

- `chat_client/endpoints/`: route handlers
- `chat_client/repositories/`: database access
- `chat_client/core/`: shared app logic
- `chat_client/templates/` and `chat_client/static/`: UI
- `tests/`: backend and Playwright tests

## Setup

```bash
uv venv
source .venv/bin/activate
uv pip install -e .
chat-client init-system
```

## Commands

- Dev server: `chat-client server-dev`
- Prod server: `chat-client server-prod`
- Checks: `bin/check_code.sh`
- Backend tests: `python tests/run_all_tests.py`
- Smoke test: `python tests/test_starlette_simple.py`

## Notes

- Keep endpoint handlers thin; move reusable logic into `core` or `repositories`.
- Do not commit secrets to `data/config.py`.
- Do not edit migration history unless the task is explicitly about migrations.
- If behavior changes, update tests in `tests/`.
