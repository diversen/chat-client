import os
import sys
import click
import subprocess
import logging
import asyncio
import secrets
import chat_client.core.set_system_path  # noqa
from chat_client.models.user_model import _password_hash
from chat_client.database.migration import Migration
from data.config import DATA_DIR, LOG_LEVEL
from chat_client import __version__, __program__
from chat_client.core.logging import setup_logging
from chat_client._models import User
from chat_client.database.db_session import async_session
from sqlalchemy import select
from pathlib import Path


setup_logging(LOG_LEVEL)
logging.basicConfig(level=logging.DEBUG)
logger: logging.Logger = logging.getLogger(__name__)


@click.group()
@click.version_option(version=__version__, prog_name=__program__)
def cli():
    """
    Simple http server for serving LLM models
    """
    pass


def _before_server_start():
    # Setup data directory
    logger.info(f"Data directory: {DATA_DIR}")
    os.makedirs(DATA_DIR, exist_ok=True)

    # Setup database path
    database_path = os.path.join(DATA_DIR, "database.db")
    logger.info(f"Database path: {database_path}")

    # Setup migrations
    migrations_path = str(Path(__file__).resolve().parent / "migrations")
    migration_manager = Migration(database_path, migrations_path)
    migration_manager.run_migrations()
    migration_manager.close()


@cli.command(help="Start the running Uvicorn dev-server. Notice: By default it watches for changes in current dir.")
@click.option("--port", default=8000, help="Server port.")
@click.option("--workers", default=4, help="Number of workers.")
@click.option("--host", default="0.0.0.0", help="Server host.")
@click.option("--log-level", default="info", help="Log level.")
def server_dev(port: int, workers: int, host: str, log_level: str):
    _before_server_start()

    reload_dirs = ["."]

    cmd = [
        sys.executable,
        "-m",
        "uvicorn",
        "chat_client.main:app",
        f"--host={host}",
        f"--port={port}",
        f"--workers={workers}",
        f"--log-level={log_level}",
    ]

    cmd.append("--reload")
    for dir in reload_dirs:
        cmd.append(f"--reload-dir={dir}")

    try:
        logger.info("Started Uvicorn in the foreground")
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Uvicorn failed to start: {e}")
        exit(1)


@cli.command(help="Start the production gunicorn server.")
@click.option("--port", default=8000, help="Server port.")
@click.option("--workers", default=3, help="Number of workers.")
@click.option("--host", default="0.0.0.0", help="Server host.")
def server_prod(port: int, workers: int, host: str):
    _before_server_start()

    if os.name == "nt":
        logger.info("Gunicorn does not work on Windows. Use server-dev instead.")
        exit(1)

    cmd = [
        # Notice that this can not just be "gunicorn" as it is a new subprocess being started
        sys.executable,
        "-m",
        "gunicorn",
        "chat_client.main:app",
        f"--workers={workers}",
        f"--bind={host}:{port}",
        "--worker-class=uvicorn.workers.UvicornWorker",
        "--log-level=info",
    ]

    try:
        logger.info("Started Gunicorn in the foreground")
        subprocess.run(cmd, check=True)
    except subprocess.CalledProcessError as e:
        logger.error(f"Gunicorn failed to start: {e}")
        exit(1)


# Command for generating a user
@cli.command(help="Create a user")
@click.option("--email", prompt="Email", help="Email")
@click.option("--password", prompt="Password", help="Password")
def create_user(email: str, password: str):
    asyncio.run(_create_user(email, password))


async def _create_user(email: str, password: str):
    password_hash = _password_hash(password)

    async with async_session() as session:
        # Check if user with email already exists
        stmt = select(User).where(User.email == email)
        result = await session.execute(stmt)
        existing_user = result.scalar_one_or_none()

        if existing_user:
            logger.info("User already exists. Please login or reset your password.")
            return

        # Insert new user
        new_user = User(
            email=email,
            password_hash=password_hash,
            verified=1,
            random=secrets.token_urlsafe(32),
        )
        session.add(new_user)
        await session.commit()


@cli.command(help="Init the system")
def init_system():

    # run migrations
    _before_server_start()
    user_message = """Migrations have been run. You may now run the server with the command"""
    logger.info(user_message)

    exit(0)
