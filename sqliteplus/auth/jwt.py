from datetime import datetime, timedelta, timezone
import os
from typing import Final

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

# Configuración de seguridad
_SECRET_KEY_ENV: Final[str] = "SECRET_KEY"
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")


def _get_secret_key() -> str:
    """Obtiene la clave secreta desde el entorno o levanta un error descriptivo."""

    secret_key = os.getenv(_SECRET_KEY_ENV)
    if not secret_key:
        raise RuntimeError(
            "SECRET_KEY debe definirse en el entorno antes de iniciar la aplicación"
        )
    return secret_key


def get_secret_key() -> str:
    """Versión pública para obtener la clave secreta configurada."""

    return _get_secret_key()


def generate_jwt(username: str):
    expiration = datetime.now(timezone.utc) + timedelta(hours=1)
    payload = {"sub": username, "exp": expiration}
    secret_key = _get_secret_key()
    return jwt.encode(payload, secret_key, algorithm=ALGORITHM)


def verify_jwt(token: str = Depends(oauth2_scheme)) -> str:
    """
    Verifica y decodifica el token JWT. Devuelve el nombre de usuario.
    """
    try:
        secret_key = _get_secret_key()
    except RuntimeError as exc:
        raise HTTPException(
            status_code=500,
            detail=str(exc),
            headers={"WWW-Authenticate": "Bearer"},
        ) from exc

    try:
        payload = jwt.decode(token, secret_key, algorithms=[ALGORITHM])
        subject = payload.get("sub") if isinstance(payload, dict) else None
        if not subject:
            raise HTTPException(
                status_code=401,
                detail="Token inválido: sujeto no disponible",
                headers={"WWW-Authenticate": "Bearer"},
            )
        return subject
    except jwt.ExpiredSignatureError:
        raise HTTPException(
            status_code=401,
            detail="Token expirado",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except (jwt.InvalidTokenError, KeyError):
        raise HTTPException(
            status_code=401,
            detail="Token inválido",
            headers={"WWW-Authenticate": "Bearer"},
        )
