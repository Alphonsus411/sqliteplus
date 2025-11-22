"""Implementación mínima de :mod:`bcrypt` para entornos sin la dependencia opcional."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from typing import Final

__all__ = ["gensalt", "hashpw", "checkpw", "is_compat_hash", "COMPAT_PREFIX"]

COMPAT_PREFIX: Final[str] = "compatbcrypt$"
_ITERATIONS: Final[int] = 390_000
_SALT_BYTES: Final[int] = 16


def _ensure_bytes(value: bytes | str, *, name: str) -> bytes:
    if isinstance(value, bytes):
        return value
    if isinstance(value, str):
        try:
            return value.encode("utf-8")
        except UnicodeEncodeError as exc:
            raise ValueError(f"{name} debe ser representable en UTF-8") from exc
    raise TypeError(f"{name} debe ser bytes o str")


def gensalt(rounds: int | None = None) -> bytes:  # type: ignore[override]
    """Genera un *salt* pseudoaleatorio."""

    _ = rounds  # Se acepta el parámetro por compatibilidad.
    random_bytes = os.urandom(_SALT_BYTES)
    salt_token = base64.urlsafe_b64encode(random_bytes).rstrip(b"=")
    return (COMPAT_PREFIX + salt_token.decode("ascii")).encode("ascii")


def _derive_digest(password: bytes, salt_token: str) -> str:
    digest = hashlib.pbkdf2_hmac("sha256", password, salt_token.encode("ascii"), _ITERATIONS)
    return base64.urlsafe_b64encode(digest).rstrip(b"=").decode("ascii")


def hashpw(password: bytes | str, salt: bytes | str) -> bytes:
    """Calcula un hash determinista compatible con :func:`checkpw`."""

    password_bytes = _ensure_bytes(password, name="password")
    salt_bytes = _ensure_bytes(salt, name="salt")

    try:
        salt_str = salt_bytes.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("salt debe ser ASCII") from exc

    if salt_str.startswith(COMPAT_PREFIX):
        salt_token = salt_str[len(COMPAT_PREFIX) :]
    else:
        salt_token = salt_str

    digest_token = _derive_digest(password_bytes, salt_token)
    return f"{COMPAT_PREFIX}{salt_token}${digest_token}".encode("ascii")


def checkpw(password: bytes | str, hashed_password: bytes | str) -> bool:
    """Valida ``password`` contra ``hashed_password`` generado con :func:`hashpw`."""

    password_bytes = _ensure_bytes(password, name="password")
    hashed_bytes = _ensure_bytes(hashed_password, name="hashed_password")

    try:
        hashed_str = hashed_bytes.decode("ascii")
    except UnicodeDecodeError as exc:
        raise ValueError("El hash almacenado es inválido: no es ASCII") from exc

    if not hashed_str.startswith(COMPAT_PREFIX):
        raise ValueError("Hash incompatible: no fue generado con la implementación integrada")

    try:
        _, salt_token, stored_digest = hashed_str.split("$", 2)
    except ValueError as exc:
        raise ValueError("Formato de hash inválido") from exc

    recalculated_digest = _derive_digest(password_bytes, salt_token)
    return hmac.compare_digest(recalculated_digest, stored_digest)


def is_compat_hash(hashed_password: bytes | str) -> bool:
    """Indica si ``hashed_password`` fue generado con este *fallback*.

    Se utiliza para conservar compatibilidad cuando el módulo nativo ``bcrypt``
    está disponible: ese módulo no reconoce el prefijo interno
    ``compatbcrypt$`` y fallaría al validar contraseñas almacenadas con esta
    implementación pura.
    """

    try:
        hashed_bytes = _ensure_bytes(hashed_password, name="hashed_password")
    except (TypeError, ValueError):
        return False

    try:
        hashed_str = hashed_bytes.decode("ascii")
    except UnicodeDecodeError:
        return False

    return hashed_str.startswith(COMPAT_PREFIX)
