import asyncio
import logging
import os
import subprocess
import sys

import click

from chat_client import __program__, __version__
from chat_client.core.bootstrap import bootstrap_runtime, create_local_user
from chat_client.core.logging import setup_logging

setup_logging(logging.INFO)
logger: logging.Logger = logging.getLogger(__name__)


async def _create_user(email: str, password: str) -> bool:
    return await create_local_user(email, password)


def _emit_bootstrap_messages(*, prompt_for_initial_user: bool) -> None:
    result = bootstrap_runtime(
        prompt_for_initial_user=prompt_for_initial_user,
        prompt_for_config_creation=True,
    )
    for message in result.messages():
        click.echo(message)


@click.group(invoke_without_command=True)
@click.version_option(version=__version__, prog_name=__program__)
@click.pass_context
def cli(ctx):
    """
    Simple http server for serving LLM models
    """
    if ctx.invoked_subcommand is None:
        _emit_bootstrap_messages(prompt_for_initial_user=True)
        click.echo("Run `chat-client server-dev` to start the server.")


@cli.command(help="Start the running Uvicorn dev-server. Notice: By default it watches for changes in current dir.")
@click.option("--port", default=1972, help="Server port.")
@click.option("--workers", default=4, help="Number of workers.")
@click.option("--host", default="0.0.0.0", help="Server host.")
@click.option("--log-level", default="info", help="Log level.")
def server_dev(port: int, workers: int, host: str, log_level: str):
    _emit_bootstrap_messages(prompt_for_initial_user=True)

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
        logger.error("Uvicorn failed to start: %s", e)
        raise SystemExit(1) from e


@cli.command(help="Start the production gunicorn server.")
@click.option("--port", default=1972, help="Server port.")
@click.option("--workers", default=3, help="Number of workers.")
@click.option("--host", default="0.0.0.0", help="Server host.")
def server_prod(port: int, workers: int, host: str):
    _emit_bootstrap_messages(prompt_for_initial_user=True)

    if os.name == "nt":
        logger.info("Gunicorn does not work on Windows. Use server-dev instead.")
        raise SystemExit(1)

    cmd = [
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
        logger.error("Gunicorn failed to start: %s", e)
        raise SystemExit(1) from e


@cli.command(help="Create a user")
@click.option("--email", help="Email")
@click.option("--password", help="Password")
def create_user(email: str | None, password: str | None):
    _emit_bootstrap_messages(prompt_for_initial_user=False)
    if not email:
        email = click.prompt("Email")
    if not password:
        password = click.prompt("Password", hide_input=True, confirmation_prompt=True)
    assert email is not None
    assert password is not None
    asyncio.run(create_local_user(email, password))


@cli.command(help="Init the system")
def init_system():
    _emit_bootstrap_messages(prompt_for_initial_user=True)
    click.echo("Migrations have been run. You may now run the server with `chat-client server-dev`.")
    raise SystemExit(0)


if __name__ == "__main__":
    cli()
