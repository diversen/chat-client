"""
This module contains utility functions for working with SQLite databases.

The functions in this module are used to create a transaction scope to ensure that all operations are atomic.
If a query fails, the transaction is rolled back and an exception is raised. Otherwise, the transaction is committed.

Example usage:

```
from ollma_serv.database.utils import DatabaseTransaction

database_url = "database.db"
database_transation = DatabaseTransaction(database_url)
transaction_scope = database_transation.transaction_scope

# same exmaples but using :placeholders
async def delete_user(user_id: int):
    async with transaction_scope_async() as connection:
        connection.execute("DELETE FROM users WHERE id = :user_id", {"user_id": user_id})
        connection.execute(
            "INSERT INTO deleted_user_log (user_id, message) VALUES (:user_id, :message)",
            {"user_id": user_id, "message": "User deleted"}
        )

async def get_user(user_id: int):
    async with transaction_scope_async() as connection:
        cursor = connection.execute("SELECT * FROM users WHERE id = :user_id", {"user_id": user_id})
        user = cursor.fetchone()
        return user

```
"""

import sqlite3
from contextlib import asynccontextmanager, contextmanager
import logging

logger: logging.Logger = logging.getLogger(__name__)


class DatabaseConnection:
    def __init__(self, database_url):
        self.database_url = database_url

    def get_db_connection_sync(self) -> sqlite3.Connection:
        """
        Create a synchronous database connection.
        """
        connection = sqlite3.connect(self.database_url)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL;")
        connection.execute("PRAGMA foreign_keys = ON;")
        return connection

    @contextmanager
    def transaction_scope_sync(self):
        """
        Synchronous transaction scope context manager.
        """
        if not self.database_url:
            raise ValueError("Database URL was not set")

        connection = self.get_db_connection_sync()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except sqlite3.Error:
            connection.rollback()
            raise
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()

    async def get_db_connection_async(self) -> sqlite3.Connection:
        """
        Create an asynchronous database connection.
        """
        if not self.database_url:
            raise ValueError("Database URL was not set")

        connection = sqlite3.connect(self.database_url)
        connection.row_factory = sqlite3.Row
        connection.execute("PRAGMA journal_mode=WAL;")
        return connection

    @asynccontextmanager
    async def async_transaction_scope(self):
        """
        Asynchronous transaction scope context manager.
        """
        connection = await self.get_db_connection_async()
        try:
            connection.execute("BEGIN IMMEDIATE")
            yield connection
            connection.commit()
        except sqlite3.Error:
            connection.rollback()
            raise
        except Exception:
            connection.rollback()
            raise
        finally:
            connection.close()
