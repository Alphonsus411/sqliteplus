import sqlite3
import threading
import os

from sqliteplus.utils.constants import DEFAULT_DB_PATH


class SQLitePlusQueryError(RuntimeError):
    """Excepción personalizada para errores en consultas SQL."""

    def __init__(self, query: str, original_exception: sqlite3.Error):
        self.query = query
        self.original_exception = original_exception
        message = f"Error al ejecutar la consulta SQL '{query}': {original_exception}"
        super().__init__(message)

class SQLitePlus:
    """
    Manejador de SQLite mejorado con soporte para concurrencia y manejo seguro de consultas.
    """

    def __init__(self, db_path=DEFAULT_DB_PATH):
        self.db_path = os.path.abspath(db_path)
        directory = os.path.dirname(self.db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self.lock = threading.Lock()
        self._initialize_db()

    def _initialize_db(self):
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            conn.commit()

    def get_connection(self):
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def execute_query(self, query, params=()):
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(query, params)
                    conn.commit()
                    return cursor.lastrowid
                except sqlite3.Error as e:
                    raise SQLitePlusQueryError(query, e) from e

    def fetch_query(self, query, params=()):
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(query, params)
                    return cursor.fetchall()
                except sqlite3.Error as e:
                    raise SQLitePlusQueryError(query, e) from e

    def log_action(self, action):
        self.execute_query("INSERT INTO logs (action) VALUES (?)", (action,))


if __name__ == "__main__":
    db = SQLitePlus()
    db.log_action("Inicialización del sistema")
    print("SQLitePlus está listo para usar.")
