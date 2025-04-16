import sqlite3
import json
import time
from typing import Any


class DatabaseCache:
    def __init__(self, connection: sqlite3.Connection):
        """
        Initialize the DatabaseCache with a connection.
        The connection is expected to be managed externally (e.g., with async with).
        """
        self.connection = connection

    async def set(self, key: str, data: Any) -> bool:
        """
        Set a cache value. This will always delete the old value and insert a new one.
        """
        json_data = json.dumps(data)
        self.connection.execute("DELETE FROM cache WHERE key = :key", {"key": key})
        self.connection.execute(
            "INSERT INTO cache (key, value, unix_timestamp) VALUES (:key, :value, :timestamp)",
            {"key": key, "value": json_data, "timestamp": int(time.time())},
        )
        return True

    async def get(self, key: str, expire_in: int = 0) -> Any:
        """
        Will return the value if the key exists and is not expired.
        Will return None if the key does not exist or if the key is expired.
        If expire_in is 0, the value will never expire.
        """
        result = self.connection.execute("SELECT * FROM cache WHERE key = :key", {"key": key}).fetchone()

        if result:
            if expire_in == 0:
                return json.loads(result["value"])

            current_time = int(time.time())
            if current_time - result["unix_timestamp"] < expire_in:
                return json.loads(result["value"])
            else:
                self.connection.execute("DELETE FROM cache WHERE id = :id", {"id": result["id"]})
        return None

    async def delete(self, id: int) -> None:
        """
        Delete a cache value by id
        """
        self.connection.execute("DELETE FROM cache WHERE id = :id", {"id": id})
        return None
