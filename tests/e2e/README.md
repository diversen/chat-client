# Playwright E2E Tests

These tests support two run modes.

## 1) Managed server mode (default)

`npm run e2e` starts its own server on `http://127.0.0.1:8010` and bootstraps a test user.

Examples:

```bash
npm run e2e
npm run e2e:headed
npm run e2e:ui
```

This mode runs startup commands equivalent to:

- `chat-client init-system`
- `chat-client create-user --email playwright@example.com --password Playwright123!`
- `uvicorn chat_client.main:app --host 127.0.0.1 --port 8010`

## 2) Use an already running server

Use the `external` scripts when the app is already running at `http://localhost:8000`.

Example:

```bash
chat-client server-dev
# in another terminal
E2E_EMAIL=test E2E_PASSWORD=test npm run e2e:external
```

## Credentials

By default, tests log in with:

- email: `playwright@example.com`
- password: `Playwright123!`

Override with env vars when needed:

```bash
E2E_EMAIL=your_email E2E_PASSWORD=your_password npm run e2e
E2E_EMAIL=your_email E2E_PASSWORD=your_password npm run e2e:external
```
