import os
from unittest import mock

import pytest
from fastapi import HTTPException

from sqliteplus.core.db import AsyncDatabaseManager


@pytest.mark.asyncio
async def test_async_manager_accepts_cipher_when_support_present(tmp_path):
    async def fake_execute(sql, *_):
        cursor = mock.AsyncMock()
        if sql == "PRAGMA cipher_version;":
            cursor.fetchone = mock.AsyncMock(return_value=("4.5.0",))
        return cursor

    fake_connection = mock.AsyncMock()
    fake_connection.execute.side_effect = fake_execute
    fake_connection.commit = mock.AsyncMock()
    fake_connection.close = mock.AsyncMock()

    with mock.patch("sqliteplus.core.db.aiosqlite.connect", new=mock.AsyncMock(return_value=fake_connection)):
        with mock.patch.dict(os.environ, {"SQLITE_DB_KEY": "secret"}, clear=False):
            manager = AsyncDatabaseManager(base_dir=tmp_path)
            connection = await manager.get_connection("secure_async")

    assert connection is fake_connection
    fake_connection.close.assert_not_awaited()
    await manager.close_connections()


@pytest.mark.asyncio
async def test_async_manager_rejects_when_cipher_pragma_is_empty(tmp_path):
    async def fake_execute(sql, *_):
        cursor = mock.AsyncMock()
        if sql == "PRAGMA cipher_version;":
            cursor.fetchone = mock.AsyncMock(return_value=("",))
        return cursor

    fake_connection = mock.AsyncMock()
    fake_connection.execute.side_effect = fake_execute
    fake_connection.commit = mock.AsyncMock()
    fake_connection.close = mock.AsyncMock()

    with mock.patch("sqliteplus.core.db.aiosqlite.connect", new=mock.AsyncMock(return_value=fake_connection)):
        with mock.patch.dict(os.environ, {"SQLITE_DB_KEY": "secret"}, clear=False):
            manager = AsyncDatabaseManager(base_dir=tmp_path)
            with pytest.raises(HTTPException, match="políticas de seguridad") as exc:
                await manager.get_connection("unsupported_async")

    assert exc.value.status_code == 503
    fake_connection.close.assert_awaited_once()


@pytest.mark.asyncio
async def test_async_manager_rejects_blank_cipher_key_even_if_not_required(tmp_path):
    fake_connection = mock.AsyncMock()
    fake_connection.execute = mock.AsyncMock(return_value=mock.AsyncMock())
    fake_connection.commit = mock.AsyncMock()
    fake_connection.close = mock.AsyncMock()

    with mock.patch("sqliteplus.core.db.aiosqlite.connect", new=mock.AsyncMock(return_value=fake_connection)):
        with mock.patch.dict(os.environ, {"SQLITE_DB_KEY": "   "}, clear=False):
            manager = AsyncDatabaseManager(base_dir=tmp_path, require_encryption=False)
            with pytest.raises(HTTPException, match="políticas de seguridad") as exc:
                await manager.get_connection("blank_key_async")

    assert exc.value.status_code == 503
    fake_connection.close.assert_awaited_once()
