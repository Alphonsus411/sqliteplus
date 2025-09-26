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
