"""Servicios de gestión de usuarios para la autenticación."""

from __future__ import annotations

if __name__ == "__main__" and __package__ in {None, ""}:
    import sys
    from pathlib import Path
    from runpy import run_module

    package_root = Path(__file__).resolve().parents[2]
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    run_module("sqliteplus.auth.users", run_name="__main__")
    raise SystemExit()

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Tuple

from sqliteplus._compat import ensure_bcrypt

bcrypt = ensure_bcrypt()


class UserSourceError(RuntimeError):
    """Señala problemas para cargar la fuente de usuarios."""


@dataclass
class UserCredentialsService:
    """Servicio que valida credenciales de usuario contra contraseñas hasheadas."""

    users: Dict[str, str]

    @classmethod
    def from_env(cls) -> "UserCredentialsService":
        """Crea el servicio leyendo la ruta configurada en ``SQLITEPLUS_USERS_FILE``."""

        users_file = os.getenv("SQLITEPLUS_USERS_FILE")
        if not users_file:
            raise UserSourceError("La variable de entorno 'SQLITEPLUS_USERS_FILE' no está definida")

        path = Path(users_file).expanduser()
        if not path.exists():
            raise UserSourceError(f"El archivo de usuarios '{users_file}' no existe")

        path = path.resolve()

        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise UserSourceError("El archivo de usuarios contiene JSON inválido") from exc

        if not isinstance(data, dict):
            raise UserSourceError("El archivo de usuarios debe contener un objeto JSON con usuarios")

        return cls(users={str(key): str(value) for key, value in data.items()})

    def verify_credentials(self, username: str, password: str) -> bool:
        """Valida que el usuario exista y que la contraseña coincida."""

        stored_hash = self.users.get(username)
        if not stored_hash:
            return False
        try:
            return bcrypt.checkpw(password.encode("utf-8"), stored_hash.encode("utf-8"))
        except ValueError:
            # bcrypt.checkpw lanza ValueError si el hash no es válido.
            return False


_cached_service: UserCredentialsService | None = None
_cached_source_signature: Tuple[str, int, int] | None = None


def _read_source_signature(path: Path) -> Tuple[str, int, int]:
    """Obtiene una firma basada en metadatos del archivo para detectar cambios.

    Se espera que ``path`` ya esté expandido y, en la medida de lo posible, resuelto
    antes de invocar esta función, de forma que la firma sea consistente.
    """

    try:
        stat_result = path.stat()
    except OSError as exc:
        raise UserSourceError(f"No se puede acceder al archivo de usuarios: {exc}") from exc

    return (str(path), int(stat_result.st_mtime_ns), stat_result.st_size)


def get_user_service() -> UserCredentialsService:
    """Obtiene (con caché) el servicio configurado de credenciales."""

    global _cached_service, _cached_source_signature

    users_file = os.getenv("SQLITEPLUS_USERS_FILE")
    if not users_file:
        raise UserSourceError("La variable de entorno 'SQLITEPLUS_USERS_FILE' no está definida")

    path = Path(users_file).expanduser()
    if not path.exists():
        raise UserSourceError(f"El archivo de usuarios '{users_file}' no existe")

    path = path.resolve()

    source_signature = _read_source_signature(path)

    if _cached_service is None or _cached_source_signature != source_signature:
        service = UserCredentialsService.from_env()
        _cached_service = service
        _cached_source_signature = source_signature

    return _cached_service


def reload_user_service() -> UserCredentialsService:
    """Fuerza la recarga inmediata del servicio de credenciales desde el archivo."""

    global _cached_service, _cached_source_signature

    service = UserCredentialsService.from_env()
    users_file = os.getenv("SQLITEPLUS_USERS_FILE")
    if not users_file:
        raise UserSourceError("La variable de entorno 'SQLITEPLUS_USERS_FILE' no está definida")

    path = Path(users_file).expanduser()
    if path.exists():
        path = path.resolve()

    _cached_service = service
    _cached_source_signature = _read_source_signature(path)
    return service


def reset_user_service_cache() -> None:
    """Reinicia la caché del servicio para pruebas o recarga de configuración."""

    global _cached_service, _cached_source_signature
    _cached_service = None
    _cached_source_signature = None
