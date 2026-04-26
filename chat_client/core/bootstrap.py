import asyncio
import importlib
import logging
import sys
from dataclasses import dataclass
from pathlib import Path

import click
from sqlalchemy import func, select

from chat_client.core.logging import setup_logging

logger: logging.Logger = logging.getLogger(__name__)

# Ensure the current working directory is importable so `data.config` resolves.
if "." not in sys.path:
    sys.path.insert(0, ".")


@dataclass(frozen=True)
class ConfigBootstrapResult:
    created: bool
    data_dir: Path
    config_path: Path


@dataclass(frozen=True)
class RuntimeBootstrapResult:
    config_bootstrap: ConfigBootstrapResult
    database_path: Path
    database_created: bool
    user_message: str | None

    def messages(self) -> list[str]:
        items: list[str] = []
        if self.config_bootstrap.created:
            items.append(f"Created default config at {self.config_bootstrap.config_path}")
        if self.database_created:
            items.append(f"Initialized database at {self.database_path}")
        else:
            items.append(f"Database is ready at {self.database_path}")
        if self.user_message:
            items.append(self.user_message)
        return items


def ensure_runtime_config(*, prompt_before_create: bool = False, allow_create: bool = True) -> ConfigBootstrapResult:
    data_dir = Path("data")
    config_path = data_dir / "config.py"
    created = False
    if not config_path.exists():
        if not allow_create:
            raise click.ClickException("System is not initialized. Run `chat-client init-system` first.")
        if prompt_before_create and can_prompt_for_user():
            click.echo(f"No runtime config found at {config_path}.")
            create_now = click.confirm("Create data/config.py now?", default=True)
            if not create_now:
                raise click.ClickException("Aborted before creating runtime config.")

        data_dir.mkdir(parents=True, exist_ok=True)
        config_dist_path = Path(__file__).resolve().parent.parent / "config-dist.py"
        config_path.write_text(config_dist_path.read_text())
        created = True

    return ConfigBootstrapResult(
        created=created,
        data_dir=data_dir.resolve(),
        config_path=config_path.resolve(),
    )


def load_runtime_config(*, prompt_before_create: bool = False, allow_create: bool = True):
    ensure_runtime_config(prompt_before_create=prompt_before_create, allow_create=allow_create)
    if "data.config" in sys.modules:
        config = importlib.reload(sys.modules["data.config"])
    else:
        config = importlib.import_module("data.config")
    setup_logging(config.LOG_LEVEL)
    return config


def run_migrations(config) -> Path:
    from chat_client.database.migration import Migration

    data_dir = Path(config.DATA_DIR)
    data_dir.mkdir(parents=True, exist_ok=True)

    database_path = Path(config.DATABASE)
    logger.debug("Data directory: %s", data_dir)
    logger.debug("Database path: %s", database_path)

    migrations_path = str(Path(__file__).resolve().parent.parent / "migrations")
    migration_manager = Migration(str(database_path), migrations_path)
    migration_manager.run_migrations()
    migration_manager.close()
    return database_path.resolve()


async def count_users() -> int:
    from chat_client.database.db_session import async_session
    from chat_client.models import User

    async with async_session() as session:
        stmt = select(func.count()).select_from(User)
        count = await session.scalar(stmt)
        return count or 0


async def create_local_user(email: str, password: str) -> bool:
    from chat_client.repositories import user_repository

    result = await user_repository.create_local_user(email, password, verified=1)
    if result.created:
        logger.info("Created user: %s", result.email)
        return True

    logger.info("User already exists. Please login or reset your password.")
    return False


def can_prompt_for_user() -> bool:
    return sys.stdin.isatty() and sys.stdout.isatty()


def maybe_prompt_for_initial_user() -> str | None:
    if not can_prompt_for_user():
        return "Skipped initial user creation because no interactive terminal was detected."

    if asyncio.run(count_users()) > 0:
        return None

    click.echo("No users exist yet. Create an initial user now.")
    create_user_now = click.confirm("Create initial user?", default=True)
    if not create_user_now:
        return "Skipped initial user creation. Run `chat-client create-user` later."

    email = click.prompt("Email")
    password = click.prompt("Password", hide_input=True, confirmation_prompt=True)
    asyncio.run(create_local_user(email, password))
    return f"Created initial user: {email}"


def bootstrap_runtime(*, prompt_for_initial_user: bool, prompt_for_config_creation: bool = False) -> RuntimeBootstrapResult:
    config_bootstrap = ensure_runtime_config(prompt_before_create=prompt_for_config_creation)
    config = load_runtime_config()
    database_path = Path(config.DATABASE)
    database_created = not database_path.exists()
    database_path = run_migrations(config)

    user_message = None
    if prompt_for_initial_user:
        user_message = maybe_prompt_for_initial_user()

    return RuntimeBootstrapResult(
        config_bootstrap=config_bootstrap,
        database_path=database_path,
        database_created=database_created,
        user_message=user_message,
    )
