# Playwright E2E Tests

These tests support two run modes.

## 1) Use an already running server (default)

`npm run e2e` assumes the app is already running at `http://localhost:8000`.

Example:

```bash
chat-client server-dev
# in another terminal
E2E_EMAIL=test E2E_PASSWORD=test npm run e2e
```

## 2) Managed server mode

`npm run e2e:managed` starts its own server on `http://127.0.0.1:8010` and bootstraps a test user.

```bash
npm run e2e:managed
```

This mode runs startup commands equivalent to:

- `chat-client init-system`
- `chat-client create-user --email playwright@example.com --password Playwright123!`
- `uvicorn chat_client.main:app --host 127.0.0.1 --port 8010`

## Credentials

By default, tests log in with:

- email: `playwright@example.com`
- password: `Playwright123!`

Override with env vars when needed:

```bash
E2E_EMAIL=your_email E2E_PASSWORD=your_password npm run e2e
```
