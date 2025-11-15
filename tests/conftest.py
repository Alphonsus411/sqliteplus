import json
import os
import secrets
import tempfile
from pathlib import Path

import asyncio

import bcrypt
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport

if "SECRET_KEY" not in os.environ:
    os.environ["SECRET_KEY"] = secrets.token_urlsafe(32)

from sqliteplus.main import app  # Importa desde la nueva estructura
from sqliteplus.core.db import db_manager

from sqliteplus.auth.users import reset_user_service_cache

DB_NAME = "test_db_api"
TABLE_NAME = "logs"
TOKEN_PATH = app.url_path_for("login")


def _prepare_users_file() -> Path:
    hashed_password = bcrypt.hashpw("admin".encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    tmp_dir = Path(tempfile.gettempdir()) / "sqliteplus_tests"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    file_path = tmp_dir / "users.json"
    file_path.write_text(json.dumps({"admin": hashed_password}), encoding="utf-8")
    os.environ["SQLITEPLUS_USERS_FILE"] = str(file_path)
    return file_path


_USERS_FILE_PATH = _prepare_users_file()


@pytest.fixture(autouse=True, scope="function")
def configure_user_store():
    reset_user_service_cache()
    yield
    reset_user_service_cache()


@pytest_asyncio.fixture(scope="function")
async def client():
    await app.router.startup()
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    await app.router.shutdown()

@pytest_asyncio.fixture(scope="function")
async def auth_headers(client):
    res = await client.post(TOKEN_PATH, data={"username": "admin", "password": "admin"})
    assert res.status_code == 200
    token = res.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    await client.delete(
        f"/databases/{DB_NAME}/drop_table?table_name={TABLE_NAME}",
        headers=headers
    )

    try:
        yield headers
    finally:
        await client.delete(
            f"/databases/{DB_NAME}/drop_table?table_name={TABLE_NAME}",
            headers=headers
        )


@pytest.fixture(scope="session", autouse=True)
def close_db_manager_session():
    yield
    asyncio.run(db_manager.close_connections())
