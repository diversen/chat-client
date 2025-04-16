# chat client

Use the simple `chat-client` to chat with a local or remote LLM.

[![chat-client](docs/screenshot.png)](docs/screenshot.png)

## Requirements

Access to a chat service that can use the OpenAI API. This can be a local or remote instance of the chat service. 

Example are e.g. `ollama` or `openai` etc. 

## Features

* user authentication and registration
* highlight code
* highlight KaTeX math
* user profile
* dark and light mode
* user dialog history
* user dialog management (delete dialogs)
* copy dialog message to clipboard
* load and continue saved dialogs
* tool support (if enabled)
* python execution (if enabled)
* supports chat and openai models (and others that can use the openai api)
* easily enable all chat models (or any other provider that can use the openai api)

## Installation using pipx

Install latest version of chat-client globaly:

<!-- LATEST-VERSION-PIPX -->
	pipx install git+https://github.com/diversen/chat-client@v0.1.60

Make a dir for configuration and data:

```bash
mkdir chat_test
cd chat_test
```

Initialize the configuration and data dir:

```bash
chat-client

# Run initial migrations
chat-client init-system

# create a user
chat-client create-user

# start dev server
chat-client server-dev
```

## Upgrade using pipx

Upgrade to latest version

<!-- LATEST-VERSION-PIPX-FORCE -->
	pipx install git+https://github.com/diversen/chat-client@v0.1.60 --force

And then restart the running server instance. 

## Installation using uv and pip

```bash
git clone https://github.com/diversen/chat-client.git
cd chat-client
uv venv
source .venv/bin/activate
uv pip install -r requirements.txt
uv pip install -e .
```

## Stack

* starlette, 
* jinja2 html templates
* plain javascript.
* sqlite3 for data storage
* uvicorn or gunicorn for running a server

## Notes

Live log chat

	journalctl -u chat --no-pager --follow

MIT © [Dennis Iversen](https://github.com/diversen)
