"""
Add the path of the project to the system path so that the a config file can
be imported from where the execution is taking place.

"""

import sys
from pathlib import Path


# add "." to the system path
sys.path.insert(0, ".")

# Check if config can be imported
try:
    import config  # noqa: F401
except ImportError:

    # copy the config-dist.py file to the current directory.
    config_dist_path = Path(__file__).resolve().parent.parent / "config-dist.py"

    # copy the file to the current directory
    with open(config_dist_path, "r") as f:
        config_content = f.read()
    with open("config.py", "w") as f:
        f.write(config_content)

    user_message = """A default 'config.py' file has been created in the current working directory.
You may edit this file to e.g. allow users to register and login.
Create the database and run migrations with the command:

    ollama-client init-system

This will create a database in the data dir in the current working directory.
You may then generate a single user with the command:

    ollama-client create-user

Now you may run the server with the command:

    ollama-client server-dev"""
    print(user_message)

    exit(0)


def get_system_paths():
    """
    Get system paths
    """
    return sys.path
