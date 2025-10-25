from __future__ import annotations

import os
import sqlite3
import threading
from pathlib import Path

from sqliteplus.utils.constants import DEFAULT_DB_PATH, resolve_default_db_path


class SQLitePlusQueryError(RuntimeError):
    """Excepción personalizada para errores en consultas SQL."""

    def __init__(self, query: str, original_exception: sqlite3.Error):
        self.query = query
        self.original_exception = original_exception
        message = f"Error al ejecutar la consulta SQL '{query}': {original_exception}"
        super().__init__(message)


class SQLitePlusCipherError(RuntimeError):
    """Excepción para errores al aplicar la clave SQLCipher."""

    def __init__(self, original_exception: sqlite3.Error):
        self.original_exception = original_exception
        message = (
            "No se pudo aplicar la clave SQLCipher. Asegúrate de que tu intérprete "
            "de SQLite tiene soporte para SQLCipher antes de continuar."
        )
        super().__init__(message)


def apply_cipher_key(connection: sqlite3.Connection, cipher_key: str | None) -> None:
    """Aplica la clave de cifrado a una conexión abierta."""

    if not cipher_key:
        return

    escaped_key = cipher_key.replace("'", "''")
    try:
        connection.execute(f"PRAGMA key = '{escaped_key}';")
    except sqlite3.DatabaseError as exc:  # pragma: no cover - depende de SQLCipher
        raise SQLitePlusCipherError(exc) from exc


class SQLitePlus:
    """Manejador de SQLite con soporte para cifrado y concurrencia."""

    def __init__(
        self,
        db_path: str | os.PathLike[str] = DEFAULT_DB_PATH,
        cipher_key: str | None = None,
    ):
        raw_path = Path(db_path)
        if raw_path == Path(DEFAULT_DB_PATH):
            resolved_db_path = resolve_default_db_path()
        else:
            resolved_db_path = raw_path
        self.db_path = os.path.abspath(resolved_db_path)
        self.cipher_key = cipher_key if cipher_key is not None else os.getenv("SQLITE_DB_KEY")
        directory = os.path.dirname(self.db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self.lock = threading.Lock()
        self._initialize_db()

    def _initialize_db(self) -> None:
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

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        try:
            apply_cipher_key(conn, self.cipher_key)
        except SQLitePlusCipherError:
            conn.close()
            raise
        return conn

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
