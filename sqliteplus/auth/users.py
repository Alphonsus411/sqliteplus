"""Servicios de gestión de usuarios para la autenticación."""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Dict

import bcrypt


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

        path = Path(users_file)
        if not path.exists():
            raise UserSourceError(f"El archivo de usuarios '{users_file}' no existe")

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


def get_user_service() -> UserCredentialsService:
    """Obtiene (con caché) el servicio configurado de credenciales."""

    global _cached_service
    if _cached_service is None:
        _cached_service = UserCredentialsService.from_env()
    return _cached_service


def reset_user_service_cache() -> None:
    """Reinicia la caché del servicio para pruebas o recarga de configuración."""

    global _cached_service
    _cached_service = None
