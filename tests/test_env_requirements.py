"""Pruebas para validar que tests/test3.py exige claves seguras del entorno."""

import os
import subprocess
import sys


def test_security_script_fails_without_secret_key():
    """El script debe abortar si SECRET_KEY no está definida."""

    env = os.environ.copy()
    env.pop("SECRET_KEY", None)
    env["SQLITE_DB_KEY"] = "clave_super_segura_de_prueba"

    result = subprocess.run(
        [sys.executable, os.path.join("tests", "test3.py")],
        capture_output=True,
        text=True,
        env=env,
        check=False,
    )

    assert result.returncode != 0
    assert "SECRET_KEY" in (result.stderr + result.stdout)
