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
    data_dir_abs = data_dir.resolve()

    # copy the config-dist.py file to the current directory.
    config_dist_path = Path(__file__).resolve().parent.parent / "config-dist.py"

    # copy the file to the current directory
    with open(config_dist_path, "r") as f:
        config_content = f.read()

    # write the content to ./data/config.py
    config_path = Path("data") / "config.py"
    with open(config_path, "w") as f:
        f.write(config_content)
    config_path_abs = config_path.resolve()

    user_message = f"""A default 'config.py' file has been created.

Config file path: {config_path_abs}
Data directory path: {data_dir_abs}

You may edit this file in order to e.g. allow users to register and login.
Or add other models and providers that supports the openai API.

Create the database and run migrations with the command:

    chat-client init-system

This will create the default database in:

    {data_dir_abs / "database.db"}

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
