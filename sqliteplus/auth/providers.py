from abc import ABC, abstractmethod
import json
import logging
import os
from pathlib import Path
from typing import Dict, Tuple

logger = logging.getLogger(__name__)


class UserSourceError(RuntimeError):
    """Señala problemas para cargar la fuente de usuarios."""


class UserProvider(ABC):
    """Interfaz para obtener credenciales de usuarios."""

    @abstractmethod
    def get_users(self) -> Dict[str, str]:
        """Devuelve un diccionario {username: bcrypt_hash}."""
        pass

    @abstractmethod
    def get_source_signature(self) -> Tuple[str, int, int] | None:
        """Devuelve una firma para detectar cambios en la fuente."""
        pass


class JsonFileUserProvider(UserProvider):
    """Proveedor que lee usuarios desde un archivo JSON especificado en el entorno."""

    def __init__(self):
        self.path = self._resolve_users_file_path()

    def _resolve_users_file_path(self) -> Path:
        users_file = os.getenv("SQLITEPLUS_USERS_FILE")
        if not users_file:
            raise UserSourceError("La variable de entorno 'SQLITEPLUS_USERS_FILE' no está definida")

        path = Path(users_file).expanduser()
        if not path.exists():
            raise UserSourceError(f"El archivo de usuarios '{users_file}' no existe")

        try:
            path = path.resolve()
        except OSError as exc:
            raise UserSourceError(
                f"No se puede resolver la ruta del archivo de usuarios '{users_file}': {exc}"
            ) from exc

        if not path.is_file():
            raise UserSourceError(
                f"El archivo de usuarios '{path}' debe ser un archivo regular"
            )

        if os.name == "posix":
            try:
                mode = path.stat().st_mode & 0o777
            except OSError as exc:
                raise UserSourceError(
                    f"No se puede leer el modo de permisos del archivo de usuarios '{path}': {exc}"
                ) from exc

            weak_mask = 0o077
            weak_bits = mode & weak_mask
            if weak_bits:
                allow_weak_perms = os.getenv("SQLITEPLUS_ALLOW_WEAK_USERS_FILE_PERMS") == "1"
                message = (
                    "Permisos inseguros en el archivo de usuarios: "
                    f"{path} tiene modo {mode:03o}; usa chmod 600 para restringir acceso. "
                    "Si necesitas compatibilidad legacy, define "
                    "SQLITEPLUS_ALLOW_WEAK_USERS_FILE_PERMS=1 explícitamente."
                )
                if allow_weak_perms:
                    logger.warning("%s", message)
                else:
                    raise UserSourceError(message)

        return path

    def get_users(self) -> Dict[str, str]:
        try:
            raw_content = self.path.read_text(encoding="utf-8")
        except OSError as exc:
            raise UserSourceError(
                f"No se pudo leer el archivo de usuarios '{self.path}': {exc}"
            ) from exc

        try:
            data = json.loads(raw_content)
        except json.JSONDecodeError as exc:
            raise UserSourceError("El archivo de usuarios contiene JSON inválido") from exc

        if not isinstance(data, dict):
            raise UserSourceError("El archivo de usuarios debe contener un objeto JSON con usuarios")

        return {str(key): str(value) for key, value in data.items()}

    def get_source_signature(self) -> Tuple[str, int, int]:
        try:
            stat_result = self.path.stat()
        except OSError as exc:
            raise UserSourceError(f"No se puede acceder al archivo de usuarios: {exc}") from exc

        return (str(self.path), int(stat_result.st_mtime_ns), stat_result.st_size)
