from chat_client.tools.python_tool import python


BUILTIN_TOOL_REGISTRY = {
    "python": python,
}


BUILTIN_LOCAL_TOOL_DEFINITIONS = [
    {
        "name": "python",
        "description": "Execute Python code and return output/result.",
        "input_schema": {
            "type": "object",
            "properties": {
                "code": {
                    "type": "string",
                    "description": "Python code to execute.",
                }
            },
            "required": ["code"],
            "additionalProperties": False,
        },
    },
]
