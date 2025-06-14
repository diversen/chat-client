from alembic.config import Config
from alembic import command
import logging

logger: logging.Logger = logging.getLogger(__name__)


class Migration:
    def __init__(self, db_path: str, migrations_package: str):
        self.db_path = db_path
        self.migrations_package = migrations_package

    def get_alembic_config(self) -> Config:
        cfg = Config()
        cfg.set_main_option("script_location", self.migrations_package)
        # Alembic expects a SQLAlchemy URL
        db_url = f"sqlite:///{self.db_path}"
        cfg.set_main_option("sqlalchemy.url", db_url)
        return cfg

    def run_migrations(self):
        cfg = self.get_alembic_config()
        command.upgrade(cfg, "head")

    def close(self):
        # Not really needed for Alembic but here for symmetry
        pass
