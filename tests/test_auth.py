import asyncio
import importlib
import json
import os
import stat
import secrets
import sys
import time
from types import ModuleType

from datetime import datetime, timedelta, timezone

import pytest
from fastapi import HTTPException
from httpx import AsyncClient, ASGITransport
import jwt
import bcrypt

from sqliteplus.main import app
from sqliteplus.auth.jwt import ALGORITHM, generate_jwt, get_secret_key, verify_jwt
from sqliteplus.auth.rate_limit import (
    get_login_rate_limit_metrics,
    reset_login_rate_limiter,
)
from sqliteplus.auth.users import (
    get_user_service,
    reload_user_service,
    reset_user_service_cache,
    UserSourceError,
)
import sqliteplus.auth.users as users_module

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
        assert res.status_code == 401
        assert res.headers["WWW-Authenticate"] == "Bearer"
        assert res.json()["detail"] == "No se pudo completar la autenticación"


@pytest.mark.asyncio
async def test_jwt_token_reports_missing_secret_key(monkeypatch):
    monkeypatch.delenv("SECRET_KEY", raising=False)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(TOKEN_PATH, data={"username": "admin", "password": "admin"})

    assert res.status_code == 500
    assert res.json()["detail"] == "No se pudo generar el token de autenticación"


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
    assert res.json()["detail"] == "No se pudo inicializar el servicio de autenticación"
    assert str(users_directory.resolve()) not in res.json()["detail"]


@pytest.mark.asyncio
async def test_login_hides_users_backend_error_details(monkeypatch):
    def _broken_service():
        raise UserSourceError("backend caído en /srv/private/users.json")

    monkeypatch.setattr("sqliteplus.api.endpoints.get_user_service", _broken_service)

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        res = await ac.post(TOKEN_PATH, data={"username": "admin", "password": "admin"})

    assert res.status_code == 500
    detail = res.json()["detail"]
    assert detail == "No se pudo inicializar el servicio de autenticación"
    assert "/srv/private" not in detail
    assert "backend" not in detail.lower()


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
    assert response.json()["detail"] == "Token inválido"


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


def test_verify_jwt_rejects_missing_issuer_audience_when_strict(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", secrets.token_urlsafe(32))
    monkeypatch.setenv("JWT_STRICT_CLAIMS", "1")
    monkeypatch.setenv("JWT_ISSUER", "sqliteplus")
    monkeypatch.setenv("JWT_AUDIENCE", "sqliteplus-api")

    token_without_iss_aud = jwt.encode(
        {
            "sub": "admin",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            "iat": datetime.now(timezone.utc),
            "nbf": datetime.now(timezone.utc),
        },
        get_secret_key(),
        algorithm=ALGORITHM,
    )

    with pytest.raises(HTTPException) as excinfo:
        verify_jwt(token_without_iss_aud)

    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "Token inválido"


def test_verify_jwt_rejects_wrong_audience_when_strict(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", secrets.token_urlsafe(32))
    monkeypatch.setenv("JWT_STRICT_CLAIMS", "1")
    monkeypatch.setenv("JWT_ISSUER", "sqliteplus")
    monkeypatch.setenv("JWT_AUDIENCE", "sqliteplus-api")

    token_wrong_aud = jwt.encode(
        {
            "sub": "admin",
            "exp": datetime.now(timezone.utc) + timedelta(minutes=5),
            "iat": datetime.now(timezone.utc),
            "nbf": datetime.now(timezone.utc),
            "iss": "sqliteplus",
            "aud": "otro-audience",
        },
        get_secret_key(),
        algorithm=ALGORITHM,
    )

    with pytest.raises(HTTPException) as excinfo:
        verify_jwt(token_wrong_aud)

    assert excinfo.value.status_code == 401
    assert excinfo.value.detail == "Token inválido"


def test_jwt_rejects_short_secret(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", "demasiado-corta")

    with pytest.raises(RuntimeError) as excinfo:
        get_secret_key()

    assert "al menos 32 caracteres" in str(excinfo.value)


def test_jwt_valid_token_with_strict_claims(monkeypatch):
    monkeypatch.setenv("SECRET_KEY", secrets.token_urlsafe(32))
    monkeypatch.setenv("JWT_STRICT_CLAIMS", "1")
    monkeypatch.setenv("JWT_ISSUER", "sqliteplus")
    monkeypatch.setenv("JWT_AUDIENCE", "sqliteplus-api")

    token = generate_jwt("admin")
    subject = verify_jwt(token)

    assert subject == "admin"


def _write_users_file(path, password: str, *, timestamp_offset: float = 0.0) -> None:
    hashed_password = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")
    path.write_text(json.dumps({"admin": hashed_password}), encoding="utf-8")
    if os.name == "posix":
        path.chmod(stat.S_IRUSR | stat.S_IWUSR)
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


@pytest.mark.skipif(os.name != "posix", reason="La verificación de permisos aplica solo en POSIX")
def test_user_service_accepts_secure_users_file_permissions(tmp_path, monkeypatch):
    users_file = tmp_path / "users.json"
    _write_users_file(users_file, "safe-pass", timestamp_offset=1)
    users_file.chmod(stat.S_IRUSR | stat.S_IWUSR)

    monkeypatch.setenv("SQLITEPLUS_USERS_FILE", str(users_file))
    monkeypatch.delenv("SQLITEPLUS_ALLOW_WEAK_USERS_FILE_PERMS", raising=False)
    reset_user_service_cache()

    service = get_user_service()
    assert service.verify_credentials("admin", "safe-pass")


@pytest.mark.skipif(os.name != "posix", reason="La verificación de permisos aplica solo en POSIX")
def test_user_service_rejects_weak_users_file_permissions(tmp_path, monkeypatch):
    users_file = tmp_path / "users.json"
    _write_users_file(users_file, "weak-pass", timestamp_offset=1)
    users_file.chmod(0o644)

    monkeypatch.setenv("SQLITEPLUS_USERS_FILE", str(users_file))
    monkeypatch.delenv("SQLITEPLUS_ALLOW_WEAK_USERS_FILE_PERMS", raising=False)
    reset_user_service_cache()

    with pytest.raises(UserSourceError) as excinfo:
        get_user_service()

    message = str(excinfo.value)
    assert "Permisos inseguros" in message
    assert "chmod 600" in message


def test_verify_credentials_reports_incompatible_hash(tmp_path, monkeypatch):
    users_file = tmp_path / "users.json"
    users_file.write_text(json.dumps({"admin": "legacy"}), encoding="utf-8")
    if os.name == "posix":
        users_file.chmod(stat.S_IRUSR | stat.S_IWUSR)

    monkeypatch.setenv("SQLITEPLUS_USERS_FILE", str(users_file))
    reset_user_service_cache()
    service = get_user_service()

    def incompatible_checkpw(_password: bytes, _stored: bytes) -> bool:
        raise ValueError("Hash incompatible: no fue generado con la implementación integrada")

    monkeypatch.setattr("sqliteplus.auth.users.bcrypt.checkpw", incompatible_checkpw)

    with pytest.raises(UserSourceError) as excinfo:
        service.verify_credentials("admin", "any")

    assert "bcrypt" in str(excinfo.value)


def test_verify_credentials_accepts_compat_hash_with_native_backend(tmp_path, monkeypatch):
    compat_bcrypt = importlib.import_module("sqliteplus._compat.bcrypt")
    compat_hash = compat_bcrypt.hashpw(b"bridge-pass", compat_bcrypt.gensalt()).decode("ascii")

    users_file = tmp_path / "users.json"
    users_file.write_text(json.dumps({"admin": compat_hash}), encoding="utf-8")
    if os.name == "posix":
        users_file.chmod(stat.S_IRUSR | stat.S_IWUSR)

    monkeypatch.setenv("SQLITEPLUS_USERS_FILE", str(users_file))

    fake_native = ModuleType("bcrypt")

    def _native_checkpw(_password, hashed_password):
        hashed_str = hashed_password.decode("ascii") if isinstance(hashed_password, bytes) else str(hashed_password)
        if hashed_str.startswith("compatbcrypt$"):
            raise ValueError("Hash incompatible: generado con el fallback")
        return False

    fake_native.checkpw = _native_checkpw  # type: ignore[attr-defined]
    fake_native.hashpw = lambda password, salt: b"native"  # type: ignore[attr-defined]
    fake_native.gensalt = lambda: b"native"  # type: ignore[attr-defined]

    original_bcrypt = sys.modules.get("bcrypt")
    sys.modules["bcrypt"] = fake_native

    try:
        importlib.reload(users_module)
        users_module.reset_user_service_cache()
        service = users_module.get_user_service()
        assert service.verify_credentials("admin", "bridge-pass")
    finally:
        if original_bcrypt is None:
            sys.modules.pop("bcrypt", None)
        else:
            sys.modules["bcrypt"] = original_bcrypt
        importlib.reload(users_module)
        users_module.reset_user_service_cache()


@pytest.mark.asyncio
async def test_jwt_token_applies_rate_limit_and_recovers_after_window():
    reset_login_rate_limiter(
        max_attempts=3,
        window_seconds=1,
        base_block_seconds=1,
        max_block_seconds=2,
    )

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        for _ in range(3):
            res = await ac.post(TOKEN_PATH, data={"username": "admin", "password": "incorrecta"})
            assert res.status_code == 401

        blocked = await ac.post(TOKEN_PATH, data={"username": "admin", "password": "incorrecta"})
        assert blocked.status_code == 401
        assert blocked.headers["WWW-Authenticate"] == "Bearer"
        assert blocked.json()["detail"] == "No se pudo completar la autenticación"

        await asyncio.sleep(1.2)

        recovered = await ac.post(TOKEN_PATH, data={"username": "admin", "password": "admin"})
        assert recovered.status_code == 200


def test_failed_login_updates_rate_limit_metrics():
    reset_login_rate_limiter(
        max_attempts=2,
        window_seconds=60,
        base_block_seconds=1,
        max_block_seconds=2,
    )

    limiter_module = importlib.import_module("sqliteplus.auth.rate_limit")
    limiter = limiter_module.login_rate_limiter

    limiter.register_failure(ip="127.0.0.1", username="admin", now=10.0)
    limiter.register_failure(ip="127.0.0.1", username="admin", now=11.0)
    limiter.is_blocked(ip="127.0.0.1", username="admin", now=11.1)

    metrics = get_login_rate_limit_metrics()
    assert metrics["failed_attempts_total"] == 2
    assert metrics["rate_limit_triggered_total"] == 1
    assert metrics["blocked_requests_total"] == 1
    assert metrics["failed_by_ip"]["127.0.0.1"] == 2
    assert metrics["failed_by_user"]["admin"] == 2
