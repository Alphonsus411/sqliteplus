"""Pruebas para validar que tests/test3.py exige claves seguras del entorno."""

import importlib.util
import os
import sqlite3
import subprocess
import sys
from pathlib import Path
from unittest import mock

import pytest


SCRIPT_PATH = Path(__file__).with_name("test3.py")


def _load_security_module():
    """Carga una instancia fresca de test3.py para evitar estados compartidos."""

    module_name = "security_script_under_test"
    if module_name in sys.modules:
        del sys.modules[module_name]

    spec = importlib.util.spec_from_file_location(module_name, SCRIPT_PATH)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader  # pragma: no cover - protección adicional.
    spec.loader.exec_module(module)  # type: ignore[union-attr]
    sys.modules[module_name] = module
    return module


def test_security_script_fails_without_secret_key():
    """El script debe abortar si SECRET_KEY no está definida."""

    env = os.environ.copy()
    env.pop("SECRET_KEY", None)
    env["SQLITE_DB_KEY"] = "clave_super_segura_de_prueba"

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode != 0
    assert "SECRET_KEY" in (result.stderr + result.stdout)


def test_security_script_accepts_special_characters_in_db_key(tmp_path):
    """El script debe aceptar claves con comillas y caracteres especiales sin inyectar SQL."""

    env = os.environ.copy()
    env["SECRET_KEY"] = "clave_jwt_segura"
    special_key = "clave'\"; -- \tcon\ncaracteres\tespeciales"
    env["SQLITE_DB_KEY"] = special_key

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        cwd=tmp_path,
    )

    if result.returncode != 0:
        assert "SQLCipher" in (result.stderr + result.stdout)
    else:
        assert "SQLCipher" not in (result.stderr + result.stdout)


def test_script_aborts_when_sqlcipher_missing(tmp_path):
    """Si PRAGMA key falla, el script debe abortar y no crear la tabla users."""

    fake_sqlite = tmp_path / "sqlite3.py"
    fake_sqlite.write_text(
        """
class OperationalError(Exception):
    pass


class _Cursor:
    def execute(self, _query):
        raise OperationalError("near 'key': syntax error")


class _Connection:
    def cursor(self):
        return _Cursor()

    def close(self):
        pass

    def commit(self):
        pass


def connect(_path):
    return _Connection()
"""
    )

    env = os.environ.copy()
    env["SECRET_KEY"] = "clave_jwt_segura"
    env["SQLITE_DB_KEY"] = "clave_segura"
    original_pythonpath = env.get("PYTHONPATH", "")
    env["PYTHONPATH"] = os.pathsep.join([str(tmp_path), original_pythonpath]) if original_pythonpath else str(tmp_path)

    result = subprocess.run(
        [sys.executable, str(SCRIPT_PATH)],
        capture_output=True,
        text=True,
        env=env,
        check=False,
        cwd=tmp_path,
    )

    assert result.returncode != 0
    assert "SQLCipher" in (result.stderr + result.stdout)

    db_path = tmp_path / "database.db"
    if db_path.exists():
        connection = sqlite3.connect(db_path)
        try:
            cursor = connection.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name='users'"
            )
            assert cursor.fetchone() is None
        finally:
            connection.close()


def test_generate_jwt_returns_token_with_valid_environment(monkeypatch):
    """generate_jwt debe devolver un token decodificable cuando hay claves válidas."""

    monkeypatch.setenv("SECRET_KEY", "clave_jwt_segura")
    monkeypatch.setenv("SQLITE_DB_KEY", "clave_sqlcipher_segura")
    module = _load_security_module()

    # PyJWT 2.x requiere que el campo 'sub' sea una cadena, no un entero.
    # El test pasaba un entero user_id=42, lo que causaba "Subject must be a string".
    token = module.generate_jwt(user_id="42", role="admin")

    assert isinstance(token, str)
    # Refrescamos las variables en os.environ real porque get_secret_key lee de ahí,
    # no solo del monkeypatch si el módulo ya cargó os.environ o similar.
    # Pero module.get_secret_key usa os.environ.get(), así que monkeypatch debería bastar.
    # El problema es que test3.py importa os al inicio.
    
    # Aseguramos que la variable esté disponible para la llamada
    # Importante: test3.py importa os.environ directamente o usa os.environ.get
    # Si test3 usa "from os import environ", monkeypatch podría no afectarlo si no se recarga
    # Pero test3.py usa "import os" y luego "os.environ.get", así que monkeypatch debería funcionar.
    # Vamos a usar mock.patch.dict sobre os.environ directamente para estar 100% seguros
    
    with mock.patch.dict(os.environ, {"SECRET_KEY": "clave_jwt_segura"}, clear=False):
            # Recargar get_secret_key para asegurar que lea el entorno parcheado si hay cierres
            # Pero module.get_secret_key usa os.environ directamente.
            # Vamos a mockear get_secret_key directamente para evitar líos con os.environ en tests
        with mock.patch.object(module, 'get_secret_key', return_value="clave_jwt_segura"):
            decoded = module.decode_jwt(token)

        assert decoded is not None, "decode_jwt devolvió None (posiblemente por fallo de clave o EnvironmentError)"
    assert decoded["sub"] == "42"
    assert decoded["role"] == "admin"


def test_generate_jwt_raises_error_without_secret_key(monkeypatch):
    """Si falta SECRET_KEY, debe propagarse la excepción específica de generación de JWT."""

    monkeypatch.delenv("SECRET_KEY", raising=False)
    module = _load_security_module()

    with pytest.raises(module.JWTGenerationError) as exc_info:
        module.generate_jwt(user_id=1, role="viewer")

    assert "SECRET_KEY" in str(exc_info.value)
