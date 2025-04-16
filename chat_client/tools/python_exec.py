import subprocess
import tempfile
import config
import logging
from logging import Logger

logger: Logger = logging.getLogger(__name__)


def _generate_script(script_src):
    """
    Generate a temporary Python script file from script source.
    """
    with tempfile.NamedTemporaryFile(mode="w", delete=False) as f:
        f.write(script_src)
        f.flush()
        f.close()

        filename = f.name

    return filename


def execute(data: dict) -> str:

    logger.info(data)
    python_exec_template = getattr(config, "PYTHON_EXEC_TEMPLATE", "")
    logger.info(f"Python exec template: {python_exec_template}")

    if not python_exec_template:
        return "<strong>The server is not configured to execute Python code</strong>"
    try:
        text = data["text"]
        # remove marker
        code = text.strip()

        # Generate a temporary Python script file
        tmp_file = _generate_script(code)

        # Format the Python execution command
        PYTHON_EXEC = python_exec_template.format(filename=tmp_file)

        # Run the script and capture the output
        result = subprocess.run(
            PYTHON_EXEC,
            shell=True,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )

        # compose result as first the code and then the output
        code = f"```python\n{code}\n```"
        output = result.stdout.decode("utf-8")
        error = result.stderr.decode("utf-8")
        return_code = result.returncode

        # Add the output to the message
        if output:
            output_part = f"<strong>Output: </strong><pre>{output}</pre>"
        else:
            output_part = "<strong>Output:</strong><pre>No output</pre>"

        # Add the error or success message
        if error:
            error_part = f"<strong>Error: </strong><pre>{error}</pre>"
        else:
            error_part = "<strong>Status: </strong><pre>Script executed successfully</pre>"

        return_code_part = f"<strong>Return code: </strong>{return_code}"

        message = f"{output_part}{error_part}{return_code_part}"
        return message

    except Exception as e:
        return str(e)
