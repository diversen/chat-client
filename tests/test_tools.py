from ollama import chat


def get_weather(location: str) -> str:
    """
    Fetches the current weather for a given location.

    Args:
        location (str): The name of the city or region.

    Returns:
        str: A summary of the weather conditions.
    """
    return f"Weather in {location} is sunny 25°C"


def execute_python_code(code: str) -> str:
    """
    Execute Python code

     Args:
       code (str): The Python code to execute

     Returns:
       str: The output of the Python code

    """
    return code


def add_two_numbers(a: int, b: int) -> int:
    """
    Add two numbers

    Args:
      a (int): The first number
      b (int): The second number

    Returns:
      int: The sum of the two numbers
    """
    return a + b


def subtract_two_numbers(a: int, b: int) -> int:
    """
    Subtract two numbers
    """
    return a - b


subtract_two_numbers_tool = {
    "type": "function",
    "function": {
        "name": "subtract_two_numbers",
        "description": "Subtract two numbers",
        "parameters": {
            "type": "object",
            "required": ["a", "b"],
            "properties": {
                "a": {"type": "integer", "description": "The first number"},
                "b": {"type": "integer", "description": "The second number"},
            },
        },
    },
}

# stream = chat(
#     model="mistral-nemo:latest",
#     messages=[{"role": "user", "content": "Write a short story"}],
#     stream=True,
#     tools=[get_weather],
# )

# for chunk in stream:
#     print(chunk["message"]["content"], end="", flush=True)


from ollama import chat

messages = [
    {
        "role": "user",
        "content": "How to add multiply a numpy tensor with a scalar?",
    },
]
response = chat(
    "mistral-nemo:latest",
    messages=messages,
    stream=True,
    tools=[get_weather, add_two_numbers],
)

print(response)
for part in response:
    print(part)
    print(part["message"]["content"], end="", flush=True)

print()
