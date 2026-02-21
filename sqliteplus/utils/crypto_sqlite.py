from __future__ import annotations

from collections.abc import Callable
from typing import Any


GENERIC_SECURITY_ERROR_MESSAGE = (
    "Base de datos no disponible temporalmente por políticas de seguridad"
)


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

