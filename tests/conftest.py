import pytest
from httpx import AsyncClient, ASGITransport
from sqliteplus.main import app  # Importa desde la nueva estructura
from urllib.parse import quote

DB_NAME = "test_db_api"
TABLE_NAME = "logs"

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
