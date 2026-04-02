from chat_client.tools.python_tool import python_hardened

BUILTIN_TOOL_REGISTRY = {
    "python_hardened": python_hardened,
}


BUILTIN_LOCAL_TOOL_DEFINITIONS = [
    {
        "name": "python_hardened",
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
        "execution": {
            "mount_workspace": True,
        },
    },
]
