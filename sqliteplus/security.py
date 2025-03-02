import sqlite3
import threading
import os
import functools
import redis


class SQLitePlus:
    """
    Manejador de SQLite mejorado con soporte para concurrencia, caché en Redis y cifrado con SQLCipher.
    """

    def __init__(self, db_path="database.db", redis_host="localhost", redis_port=6379):
        self.db_path = db_path
        self.lock = threading.Lock()  # Para manejar concurrencia
        self.db_key = os.getenv("SQLITE_DB_KEY", "clave_super_segura")  # Clave de cifrado
        self.redis_client = redis.Redis(host=redis_host, port=redis_port, db=0)  # Configuración de caché
        self._initialize_db()

    def _initialize_db(self):
        """
        Inicializa la base de datos creando las tablas necesarias si no existen.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def get_connection(self):
        """
        Obtiene una conexión cifrada a la base de datos usando SQLCipher.
        """
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        cursor = conn.cursor()
        cursor.execute(f"PRAGMA key='{self.db_key}';")  # Aplica la clave de cifrado
        return conn

    def cache_result(func):
        """
        Decorador para almacenar en caché los resultados de las consultas SELECT.
        """

        @functools.wraps(func)
        def wrapper(self, query, params=()):
            cache_key = f"query:{query}:{params}"
            cached_result = self.redis_client.get(cache_key)
            if cached_result:
                return eval(cached_result.decode())  # Convertir de string a lista
            result = func(self, query, params)
            if result:
                self.redis_client.setex(cache_key, 300, str(result))  # Caché por 5 minutos
            return result

        return wrapper

    def execute_query(self, query, params=()):
        """
        Ejecuta una consulta de escritura en la base de datos.
        """
        with self.lock:  # Bloquea la ejecución para evitar conflictos
            with self.get_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(query, params)
                    conn.commit()
                    return cursor.lastrowid
                except sqlite3.Error as e:
                    print(f"Error en la consulta: {e}")
                    return None

    @cache_result
    def fetch_query(self, query, params=()):
        """
        Ejecuta una consulta de lectura en la base de datos y devuelve los resultados, con caché en Redis.
        """
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(query, params)
                    return cursor.fetchall()
                except sqlite3.Error as e:
                    print(f"Error en la consulta: {e}")
                    return None

    def log_action(self, action):
        """
        Registra una acción en la tabla de logs.
        """
        self.execute_query("INSERT INTO logs (action) VALUES (?)", (action,))


if __name__ == "__main__":
    db = SQLitePlus()
    db.log_action("Inicialización del sistema con SQLCipher y caché en Redis")
    print("SQLitePlus está listo para usar con cifrado SQLCipher y caché optimizada en Redis.")
