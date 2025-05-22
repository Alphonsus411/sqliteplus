import jwt
from datetime import datetime, timedelta, timezone
import os
from fastapi import Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer

# Configuración de seguridad
SECRET_KEY = os.getenv("SECRET_KEY", "clave_super_segura")
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
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")
