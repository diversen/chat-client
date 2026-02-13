# AGENTS

## Project Snapshot
- `chat-client` is a Python 3.10+ Starlette web app with server-rendered templates and static JS/CSS.
- Main app entrypoint: `chat_client/main.py` (`app` object).
- CLI entrypoint: `chat_client/cli.py` (`chat-client` command).
- Data and runtime config are under `data/` (especially `data/config.py` and `data/database.db`).

## Code Map
- `chat_client/endpoints/`: route handlers (`chat`, `user`, `prompt`, `error`).
- `chat_client/repositories/`: data access layer.
- `chat_client/core/`: middleware, sessions, templates, shared utilities.
- `chat_client/templates/` and `chat_client/static/`: UI.
- `tests/`: Starlette backend tests (simple + comprehensive scripts).

## Local Setup
```bash
uv venv
source .venv/bin/activate
uv pip install -e .
chat-client init-system
```

## Run
- Dev server: `chat-client server-dev`
- Prod-style server: `chat-client server-prod`

## Checks
- Format/lint/type-check: `bin/check_code.sh`
- Run tests: `python tests/run_all_tests.py`
- Faster smoke test: `python tests/test_starlette_simple.py`

## Editing Guidelines
- Keep endpoint logic thin; prefer repository/core helpers for reusable behavior.
- Avoid committing secrets or real API keys to `data/config.py`.
- Do not edit Alembic migration history unless the task is explicitly about migrations.
- If behavior changes, update or add tests in `tests/` alongside the affected endpoint area.
