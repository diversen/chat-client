# chat client

Use the simple `chat-client` to chat with a local or remote LLM.
	
[![chat-client](docs/screenshot.png)](docs/screenshot.png)

Install as a python tool and run the server. Then connect to the server using the web interface.

## Requirements

Access to a chat service that can use the OpenAI API. This can be a local or remote instance of the chat service. 

Can connect to models served by `ollama`, `vllm`, `openai`, `gemini` etc.  

## Features

* User authentication and registration
* Highlight code
* Highlight KaTeX math
* Dark and light mode
* User dialog history
* User dialog management (delete dialogs)
* Copy dialog message to clipboard
* Load and continue saved dialogs
* Upload images (use vision models)
* MCP tool support (if enabled)


## Installation using pipx

Install latest version of chat-client globally:

<!-- LATEST-VERSION-UV -->
	uv tool install git+https://github.com/diversen/chat-client@v2.3.35

Initialize the configuration and data dir:

```bash
# Generate config and data dir
chat-client

# Run initial migrations
chat-client init-system

# create a user
chat-client create-user

# start dev server. This will work if ollama is installed and running
# You should have access to all ollama models
chat-client server-dev
```

All data is stored in `./data/` directory of the running instance. E.g. `log files` and sqlite3 `database`. You should checkout the `./data/config.py` file and change the configuration to fit your needs. 

## Upgrade using uv

Upgrade to latest version

<!-- LATEST-VERSION-UV-FORCE -->
	uv tool install git+https://github.com/diversen/chat-client@v2.3.35 --force

And then restart the running server instance. 

MIT © [Dennis Iversen](https://github.com/diversen)
