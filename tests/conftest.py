import json
import os
import tempfile
from pathlib import Path

import bcrypt
import pytest
from httpx import AsyncClient, ASGITransport
from sqliteplus.main import app  # Importa desde la nueva estructura

from sqliteplus.auth.users import reset_user_service_cache

DB_NAME = "test_db_api"
TABLE_NAME = "logs"


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


@pytest.fixture(scope="function")
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

@pytest.fixture(scope="function")
async def auth_headers(client):
    res = await client.post("/token", data={"username": "admin", "password": "admin"})
    assert res.status_code == 200
    token = res.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.fixture(autouse=True, scope="function")
async def cleanup_table(client, auth_headers):
    await client.delete(
        f"/databases/{DB_NAME}/drop_table?table_name={TABLE_NAME}",
        headers=auth_headers
    )
    yield
    await client.delete(
        f"/databases/{DB_NAME}/drop_table?table_name={TABLE_NAME}",
        headers=auth_headers
    )
