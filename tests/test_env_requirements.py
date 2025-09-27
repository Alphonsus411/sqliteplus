"""Pruebas para validar que tests/test3.py exige claves seguras del entorno."""

import os
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

    assert result.returncode == 0, result.stderr + result.stdout
