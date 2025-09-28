"""Pruebas para validar que tests/test3.py exige claves seguras del entorno."""

import os
import sqlite3
import subprocess
import sys
from pathlib import Path


SCRIPT_PATH = Path(__file__).with_name("test3.py")


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
