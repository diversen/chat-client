from sqlalchemy import event
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from data.config import DATABASE
import logging

logger: logging.Logger = logging.getLogger(__name__)

logger.info("Database path: %s", DATABASE)

engine = create_async_engine(
    f"sqlite+aiosqlite:///./{DATABASE}",
    echo=False,
)

# Enable foreign keys on SQLite
@event.listens_for(engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

async_session = async_sessionmaker(engine, expire_on_commit=False)

"""
engine = create_async_engine(
    DATABASE_URL,
    future=True,
    pool_size=5,
    max_overflow=10,
    pool_timeout=30,
    echo=False,
)

"""