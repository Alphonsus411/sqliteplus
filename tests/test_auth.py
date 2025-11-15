import importlib
import json
import os
import secrets
import sys
import time

from datetime import datetime, timedelta, timezone

import pytest
from httpx import AsyncClient, ASGITransport
import jwt
import bcrypt

from sqliteplus.main import app
from sqliteplus.auth.jwt import ALGORITHM, get_secret_key
from sqliteplus.auth.users import (
    get_user_service,
    reload_user_service,
    reset_user_service_cache,
    UserSourceError,
)

TOKEN_PATH = app.url_path_for("login")


@pytest.mark.asyncio
async def test_jwt_token_success():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(TOKEN_PATH, data={"username": "admin", "password": "admin"})
        assert res.status_code == 200
        data = res.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

@pytest.mark.asyncio
async def test_jwt_token_failure():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(TOKEN_PATH, data={"username": "invalid", "password": "wrong"})
        assert res.status_code == 400
        assert res.json()["detail"] == "Credenciales incorrectas"


@pytest.mark.asyncio
async def test_jwt_token_reports_missing_secret_key(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(TOKEN_PATH, data={"username": "admin", "password": "admin"})

    assert res.status_code == 500
    assert (
        res.json()["detail"]
        == "SECRET_KEY debe definirse en el entorno antes de iniciar la aplicación"
    )


@pytest.mark.asyncio
async def test_jwt_token_reports_invalid_users_file_when_directory(tmp_path, monkeypatch):
    users_directory = tmp_path / "users"
    users_directory.mkdir()

    monkeypatch.setenv("SQLITEPLUS_USERS_FILE", str(users_directory))
    reset_user_service_cache()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(TOKEN_PATH, data={"username": "admin", "password": "admin"})

    assert res.status_code == 500
    expected_message = f"El archivo de usuarios '{users_directory.resolve()}' debe ser un archivo regular"
    assert res.json()["detail"] == expected_message


@pytest.mark.asyncio
async def test_protected_endpoint_requires_subject_claim():
    token_without_sub = jwt.encode(
        {"exp": datetime.now(timezone.utc) + timedelta(minutes=5)},
        get_secret_key(),
        algorithm=ALGORITHM,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        response = await ac.get(
            "/databases/test_db/fetch",
            params={"table_name": "validname"},
            headers={"Authorization": f"Bearer {token_without_sub}"},
        )

    assert response.status_code == 401
    assert response.json()["detail"] == "Token inválido: sujeto no disponible"


def test_jwt_requires_secret_key(monkeypatch):
    module_name = "sqliteplus.auth.jwt"
    original_secret = os.environ.get("SECRET_KEY")

    sys.modules.pop(module_name, None)
    monkeypatch.delenv("SECRET_KEY", raising=False)

    module = importlib.import_module(module_name)

    with pytest.raises(RuntimeError):
        module.get_secret_key()

    with pytest.raises(RuntimeError):
        module.generate_jwt("usuario")

    sys.modules.pop(module_name, None)

    restored_secret = original_secret or secrets.token_urlsafe(32)
    monkeypatch.setenv("SECRET_KEY", restored_secret)

    module = importlib.import_module(module_name)
    assert module.get_secret_key() == restored_secret


def _write_users_file(path, password: str, *, timestamp_offset: float = 0.0) -> None:
    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    path.write_text(json.dumps({"admin": hashed_password}), encoding="utf-8")
    new_time = time.time() + timestamp_offset
    os.utime(path, (new_time, new_time))


def test_user_service_expands_home_in_env_path(tmp_path, monkeypatch):
    home_dir = tmp_path / "home"
    home_dir.mkdir()

    monkeypatch.setenv("HOME", str(home_dir))

    users_file = home_dir / "users.json"
    _write_users_file(users_file, "home-secret", timestamp_offset=1)

    monkeypatch.setenv("SQLITEPLUS_USERS_FILE", "~/users.json")
    reset_user_service_cache()

    service = get_user_service()
    try:
        assert service.verify_credentials("admin", "home-secret")
    finally:
        reset_user_service_cache()


def test_user_service_reloads_when_file_changes(tmp_path, monkeypatch):
    users_file = tmp_path / "users.json"
    _write_users_file(users_file, "old-secret", timestamp_offset=1)

    monkeypatch.setenv("SQLITEPLUS_USERS_FILE", str(users_file))
    reset_user_service_cache()

    initial_service = get_user_service()
    assert initial_service.verify_credentials("admin", "old-secret")
    assert not initial_service.verify_credentials("admin", "new-secret")

    _write_users_file(users_file, "new-secret", timestamp_offset=2)

    refreshed_service = get_user_service()
    assert refreshed_service.verify_credentials("admin", "new-secret")
    assert not refreshed_service.verify_credentials("admin", "old-secret")


def test_reload_user_service_force_refresh(tmp_path, monkeypatch):
    users_file = tmp_path / "users.json"
    _write_users_file(users_file, "initial-pass", timestamp_offset=1)

    monkeypatch.setenv("SQLITEPLUS_USERS_FILE", str(users_file))
    reset_user_service_cache()

    service = reload_user_service()
    assert service.verify_credentials("admin", "initial-pass")

    _write_users_file(users_file, "changed-pass", timestamp_offset=2)

    reloaded_service = reload_user_service()
    assert reloaded_service.verify_credentials("admin", "changed-pass")


def test_verify_credentials_reports_incompatible_hash(tmp_path, monkeypatch):
    users_file = tmp_path / "users.json"
    users_file.write_text(json.dumps({"admin": "legacy"}), encoding="utf-8")

    monkeypatch.setenv("SQLITEPLUS_USERS_FILE", str(users_file))
    reset_user_service_cache()
    service = get_user_service()

    def incompatible_checkpw(_password: bytes, _stored: bytes) -> bool:
        raise ValueError("Hash incompatible: no fue generado con la implementación integrada")

    monkeypatch.setattr("sqliteplus.auth.users.bcrypt.checkpw", incompatible_checkpw)

    with pytest.raises(UserSourceError) as excinfo:
        service.verify_credentials("admin", "any")

    assert "bcrypt" in str(excinfo.value)
