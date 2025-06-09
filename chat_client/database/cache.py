# chat_client/cache.py

import json
import time
from typing import Any
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, delete

from chat_client.models import Cache

class DatabaseCache:
    def __init__(self, session: AsyncSession):
        """
        Initialize with an Async SQLAlchemy Session.
        """
        self.session = session

    async def set(self, key: str, data: Any) -> bool:
        """
        Set a cache value. Delete old, insert new.
        """
        # Delete existing
        await self.session.execute(
            delete(Cache).where(Cache.key == key)
        )
        # Insert new
        new_cache = Cache(
            key=key,
            value=json.dumps(data),
            unix_timestamp=int(time.time())
        )
        self.session.add(new_cache)
        await self.session.commit()
        return True

    async def get(self, key: str, expire_in: int = 0) -> Any:
        """
        Get value by key, optionally check expiration.
        """

        result = await self.session.execute(select(Cache).where(Cache.key == key))
        cache_row = result.scalar_one_or_none()

        if cache_row:
            if expire_in == 0:
                return json.loads(cache_row.value)

            current_time = int(time.time())
            if current_time - cache_row.unix_timestamp < expire_in:
                return json.loads(cache_row.value)
            else:
                # Expired — delete
                await self.session.execute(
                    delete(Cache).where(Cache.cache_id == cache_row.cache_id)
                )
                await self.session.commit()
        return None

    async def delete(self, cache_id: int) -> None:
        """
        Delete a cache value by cache_id.
        """
        await self.session.execute(
            delete(Cache).where(Cache.cache_id == cache_id)
        )
        await self.session.commit()
        return None
