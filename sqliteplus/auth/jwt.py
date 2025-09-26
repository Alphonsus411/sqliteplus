import jwt
from datetime import datetime, timedelta, timezone
import os
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

# Configuración de seguridad
SECRET_KEY = os.getenv("SECRET_KEY")

if not SECRET_KEY:
    raise RuntimeError(
        "SECRET_KEY debe definirse en el entorno antes de iniciar la aplicación"
    )
ALGORITHM = "HS256"
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")


def generate_jwt(username: str):
    expiration = datetime.now(timezone.utc) + timedelta(hours=1)
    payload = {"sub": username, "exp": expiration}
    return jwt.encode(payload, SECRET_KEY, algorithm=ALGORITHM)


def verify_jwt(token: str = Depends(oauth2_scheme)) -> str:
    """
    Verifica y decodifica el token JWT. Devuelve el nombre de usuario.
    """
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        subject = payload.get("sub") if isinstance(payload, dict) else None
        if not subject:
            raise HTTPException(
                status_code=401, detail="Token inválido: sujeto no disponible"
            )
        return subject
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except (jwt.InvalidTokenError, KeyError):
        raise HTTPException(status_code=401, detail="Token inválido")
