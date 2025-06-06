from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from data.config import DATABASE
import logging


logger: logging.Logger = logging.getLogger(__name__)

logger.info("Database path: %s", DATABASE)

# e.g. data/database.db

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
engine = create_async_engine(f"sqlite+aiosqlite:///./{DATABASE}",)
# engine = create_async_engine(f"sqlite+aiosqlite:///./chat_client.db")
async_session = async_sessionmaker(engine, expire_on_commit=False)