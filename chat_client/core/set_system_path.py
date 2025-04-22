"""
Add the path of the project to the system path so that the a config file can
be imported from where the execution is taking place.

"""

import sys
import os
from pathlib import Path


# add "." to the system path
sys.path.insert(0, ".")

# Check if config can be imported
try:
    import data.config as config  # noqa: F401
except ImportError:

    # Create 'data' directory if it does not exist
    data_dir = Path("data")
    if not data_dir.exists():
        os.makedirs(data_dir)

    # copy the config-dist.py file to the current directory.
    config_dist_path = Path(__file__).resolve().parent.parent / "config-dist.py"

    # copy the file to the current directory
    with open(config_dist_path, "r") as f:
        config_content = f.read()

    # write the content to ./data/config.py
    config_path = Path("data") / "config.py"
    with open(config_path, "w") as f:
        f.write(config_content)

    user_message = """A default 'config.py' file has been created in the current working directory.
You may edit this file to e.g. allow users to register and login.
Create the database and run migrations with the command:

    chat-client init-system

This will create a database in the data dir in the current working directory.
You may then generate a single user with the command:

    chat-client create-user

Now you may run the server with the command:

    chat-client server-dev"""
    print(user_message)

    exit(0)


def get_system_paths():
    """
    Get system paths
    """
    return sys.path
