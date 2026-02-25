from datetime import datetime, timedelta, timezone
import os
from typing import Final

import jwt
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

# Configuración de seguridad
_SECRET_KEY_ENV: Final[str] = "SECRET_KEY"
_JWT_ISSUER_ENV: Final[str] = "JWT_ISSUER"
_JWT_AUDIENCE_ENV: Final[str] = "JWT_AUDIENCE"
_JWT_STRICT_CLAIMS_ENV: Final[str] = "JWT_STRICT_CLAIMS"
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="token")


def _is_truthy(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def _requires_strict_claims() -> bool:
    return _is_truthy(os.getenv(_JWT_STRICT_CLAIMS_ENV))


def _get_issuer_and_audience() -> tuple[str | None, str | None]:
    return (os.getenv(_JWT_ISSUER_ENV), os.getenv(_JWT_AUDIENCE_ENV))


def _has_basic_entropy(secret_key: str) -> bool:
    unique_chars = len(set(secret_key))
    categories = sum(
        (
            any(char.islower() for char in secret_key),
            any(char.isupper() for char in secret_key),
            any(char.isdigit() for char in secret_key),
            any(not char.isalnum() for char in secret_key),
        )
    )
    return unique_chars >= 12 and categories >= 3


def _get_secret_key() -> str:
    """Obtiene la clave secreta desde el entorno o levanta un error descriptivo."""

    secret_key = os.getenv(_SECRET_KEY_ENV)
    if not secret_key:
        raise RuntimeError(
            "SECRET_KEY debe definirse en el entorno antes de iniciar la aplicación"
        )

    if len(secret_key) < 32:
        raise RuntimeError("SECRET_KEY debe tener al menos 32 caracteres para HS256")

    if not _has_basic_entropy(secret_key):
        raise RuntimeError(
            "SECRET_KEY no tiene suficiente entropía; usa una clave aleatoria segura"
        )

    return secret_key


def get_secret_key() -> str:
    """Versión pública para obtener la clave secreta configurada."""

    return _get_secret_key()


def generate_jwt(username: str):
    now = datetime.now(timezone.utc)
    expiration = now + timedelta(hours=1)
    issuer, audience = _get_issuer_and_audience()
    strict_claims = _requires_strict_claims()

    if strict_claims and (not issuer or not audience):
        raise RuntimeError(
            "JWT_STRICT_CLAIMS=1 requiere definir JWT_ISSUER y JWT_AUDIENCE"
        )

    payload = {
        "sub": username,
        "exp": expiration,
        "iat": now,
        "nbf": now,
    }
    if issuer:
        payload["iss"] = issuer
    if audience:
        payload["aud"] = audience

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
        issuer, audience = _get_issuer_and_audience()
        strict_claims = _requires_strict_claims()

        required_claims = ["sub", "exp", "iat", "nbf"]
        if strict_claims:
            required_claims.extend(["iss", "aud"])

        payload = jwt.decode(
            token,
            secret_key,
            algorithms=[ALGORITHM],
            issuer=issuer,
            audience=audience,
            options={
                "verify_signature": True,
                "verify_exp": True,
                "verify_iat": True,
                "verify_nbf": True,
                "verify_iss": bool(issuer),
                "verify_aud": bool(audience),
                "require": required_claims,
            },
        )
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
