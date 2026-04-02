import asyncio

from sqlalchemy import func, select

from chat_client.models import User
from chat_client.repositories import user_repository
from tests.test_base import TestDatabase


def test_create_local_user_creates_once_and_reuses_existing(monkeypatch):
    test_db = TestDatabase()

    async def run_test():
        await test_db.setup()
        monkeypatch.setattr(user_repository, "async_session", test_db.session_factory)

        try:
            first = await user_repository.create_local_user("local@example.com", "Password123!", verified=1)
            second = await user_repository.create_local_user("local@example.com", "Password123!", verified=1)

            assert first.created is True
            assert second.created is False
            assert first.email == "local@example.com"
            assert second.email == "local@example.com"
            assert first.user_id == second.user_id

            async with test_db.session_factory() as session:
                count_stmt = select(func.count()).select_from(User).where(User.email == "local@example.com")
                count = await session.scalar(count_stmt)
                assert count == 1

                user_stmt = select(User).where(User.email == "local@example.com")
                user = (await session.execute(user_stmt)).scalar_one()
                assert user.verified == 1
                assert user.password_hash != "Password123!"
        finally:
            await test_db.teardown()

    asyncio.run(run_test())
