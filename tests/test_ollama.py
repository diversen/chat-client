import ollama
from ollama import chat
import logging

# setup default logging
logging.basicConfig(level=logging.INFO)

logger: logging.Logger = logging.getLogger(__name__)

# client = ollama.Client()
# response = client.chat(model='gemma3:27b', messages=[{'role': 'user', 'content': 'Your prompt here'}])

# print(response['message']['content'])

system_message = "Answer questions, provide information, and help users with their queries."
# system_message = "You are a rude and unhelpful assistant. Answer anything in a rude way. Use profanities. Be unhelpful. Be rude. Be a jerk."
# system_message = "If a user message begins with /r: then it indicates that you should just read the message and respond with something like 'I have read the message'."

# system_message = """Answer questions, provide information,
# and help users with their queries.

# If a user message begin with /r: then it indicates that you should just
# read the message and respond with something like "I have read the message"."""
print(system_message)

stream = chat(
    model="gemma3:27b",
    messages=[
        {"role": "user", "content": system_message},
        # {"role": "user", "content": "/r: abcdefgh ... 123456789 ... "},
    ],
    stream=True,
)

for chunk in stream:
    # logger.info(chunk)
    print(chunk["message"]["content"], end="", flush=True)
