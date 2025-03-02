import sqlite3
import bcrypt
import jwt
import datetime
import os

SECRET_KEY = "supersecreto"  # Clave secreta para firmar los JWT
DB_KEY = os.getenv("SQLITE_DB_KEY", "clave_super_segura")  # Clave de cifrado para SQLCipher

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
        return jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    except Exception as e:
        print(f"Error generando JWT: {e}")
        return None

def decode_jwt(token: str):
    """
    Decodifica y verifica un JWT.
    """
    try:
        return jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
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
    cursor.execute(f"PRAGMA key='{DB_KEY}';")  # Establece la clave de cifrado
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
    create_users_table()
    print("Módulo de seguridad inicializado con cifrado SQLCipher y corrección en JWT.")
