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

import argparse
import getpass
import importlib
import logging
import sys
from dataclasses import dataclass
from pathlib import Path
from types import ModuleType
from typing import Dict, Tuple

from sqliteplus.auth.providers import JsonFileUserProvider, UserSourceError
from sqliteplus._compat import ensure_bcrypt


def _build_bcrypt_adapter() -> ModuleType:
    """Crea un adaptador que decide qué backend usar según el hash recibido."""

    primary_backend = ensure_bcrypt()
    compat_backend = importlib.import_module("sqliteplus._compat.bcrypt")

    if primary_backend is compat_backend:
        return compat_backend

    compat_prefix = getattr(compat_backend, "_PREFIX", "compatbcrypt$")

    class _BcryptAdapter(ModuleType):
        def __init__(self) -> None:
            super().__init__("bcrypt")
            self._primary = primary_backend
            self._compat = compat_backend
            self._compat_prefix = compat_prefix

        def __getattr__(self, name: str):
            return getattr(self._primary, name)

        def checkpw(self, password, hashed_password):  # type: ignore[override]
            hashed_str = _try_decode_ascii(hashed_password)
            if hashed_str is not None and hashed_str.startswith(self._compat_prefix):
                return self._compat.checkpw(password, hashed_password)
            return self._primary.checkpw(password, hashed_password)

    return _BcryptAdapter()


def _try_decode_ascii(value) -> str | None:
    if isinstance(value, str):
        return value
    if isinstance(value, (bytes, bytearray)):
        try:
            return bytes(value).decode("ascii")
        except UnicodeDecodeError:
            return None
    return None


bcrypt = _build_bcrypt_adapter()
logger = logging.getLogger(__name__)

# Hash bcrypt válido precomputado para ejecutar una verificación señuelo cuando
# el usuario no existe y así mantener un coste computacional similar.
_DUMMY_BCRYPT_HASH = (
    "compatbcrypt$-xX2q82qpzgjY5QPepN0Tw$"
    "PyYjiRJAzz0TDudvbO3ArTvNn7ac4iOvvvhm2ig2KTg"
)


@dataclass
class UserCredentialsService:
    """Servicio que valida credenciales de usuario contra contraseñas hasheadas."""

    users: Dict[str, str]

    @classmethod
    def from_env(cls) -> "UserCredentialsService":
        """Crea el servicio leyendo la ruta configurada en ``SQLITEPLUS_USERS_FILE``."""
        provider = JsonFileUserProvider()
        return cls(users=provider.get_users())

    def verify_credentials(self, username: str, password: str) -> bool:
        """Valida que el usuario exista y que la contraseña coincida."""

        stored_hash = self.users.get(username)
        user_exists = bool(stored_hash)
        hash_to_check = stored_hash or _DUMMY_BCRYPT_HASH

        try:
            password_matches = bcrypt.checkpw(
                password.encode("utf-8"), hash_to_check.encode("utf-8")
            )
        except ValueError as exc:
            # ``bcrypt`` eleva ``ValueError`` cuando el hash almacenado tiene un
            # formato incompatible (por ejemplo, si fue generado con la versión
            # nativa y actualmente sólo está disponible el *fallback* puro
            # Python).  En lugar de tratarlo como credenciales inválidas,
            # exponemos un error descriptivo para guiar al usuario.
            raise UserSourceError(
                "El hash de la contraseña configurado no es compatible con la "
                "implementación disponible de bcrypt. Instala la dependencia "
                "'bcrypt' oficial para validar credenciales."
            ) from exc

        return user_exists and password_matches


_cached_service: UserCredentialsService | None = None
_cached_source_signature: Tuple[str, int, int] | None = None


def get_user_service() -> UserCredentialsService:
    """Obtiene (con caché) el servicio configurado de credenciales."""

    global _cached_service, _cached_source_signature

    provider = JsonFileUserProvider()
    source_signature = provider.get_source_signature()

    if _cached_service is None or _cached_source_signature != source_signature:
        users = provider.get_users()
        _cached_service = UserCredentialsService(users=users)
        _cached_source_signature = source_signature

    return _cached_service


def reload_user_service() -> UserCredentialsService:
    """Fuerza la recarga inmediata del servicio de credenciales desde el archivo."""

    global _cached_service, _cached_source_signature

    provider = JsonFileUserProvider()
    users = provider.get_users()
    source_signature = provider.get_source_signature()

    service = UserCredentialsService(users=users)
    _cached_service = service
    _cached_source_signature = source_signature
    return service


def reset_user_service_cache() -> None:
    """Reinicia la caché del servicio para pruebas o recarga de configuración."""

    global _cached_service, _cached_source_signature
    _cached_service = None
    _cached_source_signature = None


def _build_cli_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m sqliteplus.auth.users",
        description="Herramientas auxiliares para gestionar usuarios de SQLitePlus.",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    hash_parser = subparsers.add_parser(
        "hash", help="Genera un hash bcrypt listo para el archivo JSON de usuarios."
    )
    hash_parser.add_argument(
        "password",
        nargs="?",
        help="Contraseña en texto plano. Si se omite se solicitará mediante getpass.",
    )
    hash_parser.add_argument(
        "-r",
        "--rounds",
        type=int,
        default=12,
        help="Número de rondas de bcrypt. Debe ser un entero entre 4 y 31 (por defecto: 12).",
    )

    return parser


def _hash_password(password: str, rounds: int) -> str:
    if not 4 <= rounds <= 31:
        raise SystemExit("--rounds debe estar entre 4 y 31")

    backend = ensure_bcrypt()
    salt = backend.gensalt(rounds=rounds)
    return backend.hashpw(password.encode("utf-8"), salt).decode("utf-8")


def _prompt_password() -> str:
    password = getpass.getpass("Contraseña: ")
    if not password:
        raise SystemExit("La contraseña no puede estar vacía")
    return password


def _main(argv: list[str] | None = None) -> int:
    parser = _build_cli_parser()
    args = parser.parse_args(argv)

    if args.command == "hash":
        password = args.password if args.password is not None else _prompt_password()
        hashed = _hash_password(password, rounds=args.rounds)
        print(hashed)
        return 0

    parser.error("Comando desconocido")
    return 1


if __name__ == "__main__":
    raise SystemExit(_main(sys.argv[1:]))
