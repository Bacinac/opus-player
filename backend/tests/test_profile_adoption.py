import asyncio
import uuid

import psycopg
import pytest
from psycopg import sql
from sqlalchemy import select
from sqlalchemy.engine import make_url
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from conftest import TEST_DATABASE_URL, run
from opus.api.routers.users import _adopt
from opus.models import User


@pytest.mark.parametrize("legacy", [False, True])
def test_concurrent_profile_adoption_preserves_one_profile_and_its_preferences(legacy):
    assert TEST_DATABASE_URL, "profile adoption tests require the container database"
    served = make_url(TEST_DATABASE_URL)
    name = "opus_adoption_" + uuid.uuid4().hex
    admin = served.set(drivername="postgresql", database="postgres")
    with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as conn:
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))

    async def scenario():
        engine = create_async_engine(served.set(database=name), poolclass=NullPool)
        sessions = async_sessionmaker(engine, expire_on_commit=False)
        try:
            async with engine.begin() as conn:
                await conn.run_sync(User.__table__.create)
            old_id = None
            if legacy:
                async with sessions() as session:
                    old = User(name="Filip", colour="#aabbcc", screensaver="household")
                    session.add(old)
                    await session.commit()
                    old_id = old.id
            gate = asyncio.Event()
            ready = 0

            async def pick():
                nonlocal ready
                async with sessions() as session:
                    assert await session.scalar(select(User).where(User.person == "filip")) is None
                    ready += 1
                    if ready == 2:
                        gate.set()
                    await gate.wait()
                    return await _adopt(session, "filip")

            tasks = [asyncio.create_task(pick()) for _ in range(2)]
            picked = await asyncio.gather(*tasks)
            assert picked[0].id == picked[1].id
            async with sessions() as session:
                rows = (await session.scalars(select(User))).all()
                assert len(rows) == 1 and rows[0].person == "filip"
                if legacy:
                    assert rows[0].id == old_id
                    assert rows[0].colour == "#aabbcc"
                    assert rows[0].screensaver == "household"
        finally:
            await engine.dispose()

    try:
        run(scenario())
    finally:
        with psycopg.connect(admin.render_as_string(hide_password=False), autocommit=True) as conn:
            conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
