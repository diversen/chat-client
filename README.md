# chat client

Use the simple `chat-client` to chat with a local or remote LLM.
	
[![chat-client](docs/screenshot.png)](docs/screenshot.png)

Install as a python tool and run the server. Then connect to the server using the web interface.

## Demo

Try the demo at: https://chat.10kilobyte.com

Use the credentials `demo:demo` to log in.

Create a user and log into the interface using `gemma3:270m` running fairly well on CPU. 

## Requirements

Access to a chat service that can use the OpenAI API. This can be a local or remote instance of a LLM server. The server should support the OpenAI API.

Can connect to models served by e.g. `ollama` or `vllm`. It can serve models from e.g. `openai` or `gemini`.  

## Features

* User authentication and registration
* Highlight code
* Highlight KaTeX math
* Dark, light, system mode
* Chat history
* Chat management (edit, continue, or delete chats)
* Copy dialog message to clipboard
* Upload images. Supports vision models.
* Custom system prompts
* Tool calling using MCP (Model-Controller-Plugin) architecture. 

## Installation using uv

Install latest version of chat-client globally:

<!-- LATEST-VERSION-UV -->
	uv tool install git+https://github.com/diversen/chat-client@v2.3.36

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
	uv tool install git+https://github.com/diversen/chat-client@v2.3.36 --force

And then restart the running server instance. 

MIT © [Dennis Iversen](https://github.com/diversen)
