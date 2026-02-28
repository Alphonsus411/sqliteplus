from __future__ import annotations

import sqlite3
from collections.abc import Callable
from typing import Any


GENERIC_SECURITY_ERROR_MESSAGE = (
    "Base de datos no disponible temporalmente por políticas de seguridad"
)


class SQLitePlusCipherError(RuntimeError):
    """Excepción para errores al aplicar la clave SQLCipher."""

    def __init__(self, original_exception: Exception | None = None, message: str | None = None):
        self.original_exception = original_exception
        detail = message or GENERIC_SECURITY_ERROR_MESSAGE
        super().__init__(detail)


def verify_cipher_support(
    *,
    cipher_key: str | None,
    cipher_version_row: Any,
    exception_factory: Callable[[str], Exception],
    security_message: str = GENERIC_SECURITY_ERROR_MESSAGE,
) -> None:
    """Valida que la clave de cifrado y el soporte SQLCipher sean utilizables."""

    if not isinstance(cipher_key, str) or cipher_key.strip() == "":
        raise exception_factory(security_message)

    if not cipher_version_row:
        raise exception_factory(security_message)

    cipher_version = cipher_version_row[0] if isinstance(cipher_version_row, (tuple, list)) else cipher_version_row
    if cipher_version is None or str(cipher_version).strip() == "":
        raise exception_factory(security_message)


def apply_cipher_key(connection: sqlite3.Connection, cipher_key: str | None) -> None:
    """Aplica la clave de cifrado a una conexión abierta y valida soporte SQLCipher."""

    if cipher_key is None:
        return

    if not isinstance(cipher_key, str):
        raise SQLitePlusCipherError(message=GENERIC_SECURITY_ERROR_MESSAGE)

    # Permitimos claves con espacios, pero no vacías
    stripped_cipher_key = cipher_key.strip()
    if not stripped_cipher_key:
        raise SQLitePlusCipherError(message="La clave de cifrado no puede estar vacía o contener solo espacios")

    # Usamos la clave original (con espacios si los tiene) para PRAGMA key
    escaped_key = cipher_key.replace("'", "''")
    try:
        connection.execute(f"PRAGMA key = '{escaped_key}';")
        cipher_version_row = connection.execute("PRAGMA cipher_version;").fetchone()
        verify_cipher_support(
            cipher_key=cipher_key,
            cipher_version_row=cipher_version_row,
            exception_factory=lambda message: SQLitePlusCipherError(message=message),
            security_message=GENERIC_SECURITY_ERROR_MESSAGE,
        )
    except sqlite3.DatabaseError as exc:  # pragma: no cover - depende de SQLCipher
        raise SQLitePlusCipherError(exc) from exc


