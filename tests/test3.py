"""Utilidades de seguridad que requieren SQLCipher para proteger la base de datos.

Si el motor SQLite utilizado no soporta SQLCipher, el script debe abortar para evitar
continuar con una base de datos sin cifrar.
"""

import datetime
import os
import sqlite3
import sys

import bcrypt
import jwt


REQUIRED_ENV_VARS = {
    "SECRET_KEY": "Clave utilizada para firmar los JWT.",
    "SQLITE_DB_KEY": "Clave de cifrado para SQLCipher.",
}


def _require_env_var(name: str) -> str:
    """Obtiene una variable de entorno obligatoria o aborta con un error descriptivo."""

    value = os.environ.get(name)
    if not value:
        raise EnvironmentError(
            f"La variable de entorno '{name}' es obligatoria para ejecutar las utilidades de seguridad."
        )
    return value


def get_secret_key() -> str:
    """Recupera la clave secreta para firmar los JWT."""

    return _require_env_var("SECRET_KEY")


def get_db_key() -> str:
    """Recupera la clave de cifrado para SQLCipher."""

    return _require_env_var("SQLITE_DB_KEY")


def ensure_required_environment() -> None:
    """Verifica que todas las variables de entorno necesarias estén disponibles."""

    for name, description in REQUIRED_ENV_VARS.items():
        if not os.environ.get(name):
            raise EnvironmentError(
                f"Falta la variable de entorno '{name}'. {description}"
            )


def hash_password(password: str) -> str:
    """
    Genera un hash seguro de la contraseña.
    """
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password.encode(), salt).decode()

def verify_password(password: str, hashed_password: str) -> bool:
    """
    Verifica si la contraseña coincide con el hash almacenado.
    """
    return bcrypt.checkpw(password.encode(), hashed_password.encode())

def generate_jwt(user_id: int, role: str) -> str:
    """
    Genera un token JWT válido.
    """
    try:
        payload = {
            "sub": user_id,
            "role": role,
            "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=2)
        }
        secret_key = get_secret_key()
        return jwt.encode(payload, secret_key, algorithm="HS256")
    except Exception as e:
        print(f"Error generando JWT: {e}")
        return None

def decode_jwt(token: str):
    """
    Decodifica y verifica un JWT.
    """
    try:
        secret_key = get_secret_key()
        return jwt.decode(token, secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        return None
    except jwt.InvalidTokenError:
        return None

def get_encrypted_connection(db_path="database.db"):
    """
    Obtiene una conexión cifrada con SQLCipher.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    db_key = get_db_key()
    escaped_key = db_key.replace("'", "''")
    try:
        cursor.execute(f"PRAGMA key = '{escaped_key}'")
    except sqlite3.OperationalError as error:
        conn.close()
        raise RuntimeError(
            "SQLCipher no está disponible; abortando para evitar crear la base de datos sin cifrar."
        ) from error
    return conn

def create_users_table(db_path="database.db"):
    """
    Crea la tabla de usuarios si no existe, usando una base de datos cifrada.
    """
    conn = get_encrypted_connection(db_path)
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            username TEXT UNIQUE,
            password TEXT,
            role TEXT
        )
        """
    )
    conn.commit()
    conn.close()

if __name__ == "__main__":
    try:
        ensure_required_environment()
        create_users_table()
    except (EnvironmentError, RuntimeError) as error:
        sys.exit(
            "No se puede inicializar el módulo de seguridad: "
            f"{error} Establece las variables y vuelve a intentarlo."
        )

    print(
        "Módulo de seguridad inicializado con cifrado habilitado y claves obtenidas desde el entorno."
    )
