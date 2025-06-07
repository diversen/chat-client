from openai import OpenAI
import os

# Get env variable GEMINI_API_KEY

API_KEY = os.getenv("GEMINI_API_KEY")

client = OpenAI(api_key=API_KEY, base_url="https://generativelanguage.googleapis.com/v1beta/openai/")

response = client.chat.completions.create(
    model="gemini-2.0-flash",
    messages=[
        # {"role": "system", "content": "You are a helpful assistant."},
        {"role": "user", "content": "Tell me a bit about yourself?"},
    ],
    stream=True,
)

for chunk in response:
    print(chunk.choices[0].delta)
