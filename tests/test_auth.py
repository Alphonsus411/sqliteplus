import importlib
import os
import secrets
import sys

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


def test_jwt_requires_secret_key(monkeypatch):
    module_name = "sqliteplus.auth.jwt"
    original_secret = os.environ.get("SECRET_KEY")

    sys.modules.pop(module_name, None)
    monkeypatch.delenv("SECRET_KEY", raising=False)

    with pytest.raises(RuntimeError):
        importlib.import_module(module_name)

    sys.modules.pop(module_name, None)

    restored_secret = original_secret or secrets.token_urlsafe(32)
    monkeypatch.setenv("SECRET_KEY", restored_secret)

    module = importlib.import_module(module_name)
    assert module.SECRET_KEY == restored_secret
