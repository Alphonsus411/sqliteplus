"""
Utilidades de seguridad que requieren SQLCipher para proteger la base de datos.

Si el motor SQLite utilizado no soporta SQLCipher, el script debe abortar para evitar
continuar con una base de datos sin cifrar. La verificación se realiza mediante
`PRAGMA cipher_version` y lanza un `RuntimeError` claro antes de manipular la base
de datos.
"""

import datetime
import os
import sqlite3
import sys

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))

try:
    import bcrypt  # type: ignore[import-not-found]
except ModuleNotFoundError:
    from sqliteplus._compat import ensure_bcrypt

    bcrypt = ensure_bcrypt()
else:
    from sqliteplus._compat import ensure_bcrypt

    bcrypt = ensure_bcrypt()

import jwt


class JWTGenerationError(RuntimeError):
    """Error específico para fallos al generar un token JWT."""

    pass


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


def ensure_sqlcipher_support() -> None:
    """Comprueba que la librería SQLite enlazada incluya soporte SQLCipher."""

    try:
        conn = sqlite3.connect(":memory:")
        cursor = conn.cursor()
        cursor.execute("PRAGMA cipher_version;")
        version = cursor.fetchone()
    except sqlite3.OperationalError as error:
        raise RuntimeError(
            "SQLCipher no está disponible en esta compilación de SQLite."
        ) from error
    finally:
        try:
            conn.close()
        except Exception:
            pass

    if not version or not any(version):
        raise RuntimeError("SQLCipher no está disponible en esta compilación de SQLite.")


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
    """Genera un token JWT válido o lanza un error descriptivo si falla."""

    payload = {
        "sub": user_id,
        "role": role,
        "exp": datetime.datetime.utcnow() + datetime.timedelta(hours=2),
    }

    try:
        secret_key = get_secret_key()
    except EnvironmentError as exc:
        raise JWTGenerationError(
            "No se puede generar un JWT porque falta la variable SECRET_KEY."
        ) from exc

    try:
        token = jwt.encode(payload, secret_key, algorithm="HS256")
    except jwt.PyJWTError as exc:
        raise JWTGenerationError("PyJWT no pudo firmar el token JWT solicitado.") from exc

    if isinstance(token, bytes):
        token = token.decode("utf-8")

    return token

def decode_jwt(token: str):
    """
    Decodifica y verifica un JWT.
    """
    try:
        secret_key = get_secret_key()
        return jwt.decode(token, secret_key, algorithms=["HS256"])
    except jwt.ExpiredSignatureError:
        print("Fallo en decode_jwt: Token expirado", file=sys.stderr)
        return None
    except jwt.InvalidTokenError as e:
        print(f"Fallo en decode_jwt: Token inválido: {e}", file=sys.stderr)
        return None
    except (EnvironmentError, OSError) as e:
        # En entornos de prueba, si la variable se borra entre llamadas,
        # get_secret_key lanza EnvironmentError (o OSError en algunos sistemas/contextos).
        # Imprimimos para depurar
        print(f"Fallo en decode_jwt por EnvironmentError al obtener SECRET_KEY: {e}", file=sys.stderr)
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
        ensure_sqlcipher_support()
        create_users_table()
    except (EnvironmentError, RuntimeError) as error:
        sys.exit(
            "No se puede inicializar el módulo de seguridad: "
            f"{error} Establece las variables y vuelve a intentarlo."
        )

    print(
        "Módulo de seguridad inicializado con cifrado habilitado y claves obtenidas desde el entorno."
    )
