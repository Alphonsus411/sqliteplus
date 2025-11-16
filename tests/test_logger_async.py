import aiosqlite
import pytest

from sqliteplus.core.logger import AsyncSQLitePlus


@pytest.mark.asyncio
async def test_async_sqliteplus_creates_database(tmp_path):
    db_file = tmp_path / "nested" / "logs.db"

    logger = AsyncSQLitePlus(db_path=db_file)
    await logger.initialize()

    resolved_path = db_file.resolve()

    assert logger.db_path == resolved_path
    assert resolved_path.exists()


@pytest.mark.asyncio
async def test_execute_query_propagates_aiosqlite_error(tmp_path):
    db_file = tmp_path / "logs.db"
    logger = AsyncSQLitePlus(db_path=db_file)
    await logger.initialize()

    with pytest.raises(aiosqlite.OperationalError):
        await logger.execute_query(
            "INSERT INTO tabla_inexistente (action) VALUES (?)", ("fallo",)
        )


@pytest.mark.asyncio
async def test_fetch_query_propagates_aiosqlite_error(tmp_path):
    db_file = tmp_path / "logs.db"
    logger = AsyncSQLitePlus(db_path=db_file)
    await logger.initialize()

    with pytest.raises(aiosqlite.OperationalError):
        await logger.fetch_query("SELECT * FROM tabla_inexistente")
