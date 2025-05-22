import pytest
from httpx import AsyncClient, ASGITransport
from sqliteplus.main import app


@pytest.mark.asyncio
async def test_jwt_token_success():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/token", data={"username": "admin", "password": "admin"})
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_jwt_token_failure():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post("/token", data={"username": "invalid", "password": "wrong"})
        assert res.status_code == 400
        assert res.json()["detail"] == "Credenciales incorrectas"
