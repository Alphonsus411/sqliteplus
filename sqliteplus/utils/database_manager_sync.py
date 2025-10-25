from __future__ import annotations

import sqlite3
import threading
from pathlib import Path


class DatabaseManager:
    """
    Gestor de bases de datos SQLite que maneja múltiples bases en paralelo
    y soporta concurrencia con `threading`.
    """

    def __init__(self, base_dir="databases"):
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)  # Asegura que el directorio exista
        self.connections = {}  # Diccionario de conexiones a bases de datos
        self.locks = {}  # Bloqueos para manejar concurrencia en cada base de datos

    def _normalize_db_name(self, raw_name: str) -> tuple[str, Path]:
        sanitized = raw_name.strip()
        if not sanitized:
            raise ValueError("Nombre de base de datos inválido")

        if any(token in sanitized for token in ("..", "/", "\\")):
            raise ValueError("Nombre de base de datos inválido")

        file_name = sanitized if sanitized.endswith(".db") else f"{sanitized}.db"
        db_path = (self.base_dir / Path(file_name)).resolve()
        if self.base_dir not in db_path.parents:
            raise ValueError("Nombre de base de datos fuera del directorio permitido")

        return db_path.stem, db_path

    def get_connection(self, db_name, *, _normalized: tuple[str, Path] | None = None):
        """
        Obtiene una conexión a la base de datos especificada.
        Si la conexión no existe, la crea.
        """
        canonical_name, db_path = _normalized or self._normalize_db_name(db_name)

        if canonical_name not in self.connections:
            self.connections[canonical_name] = sqlite3.connect(str(db_path), check_same_thread=False)
            self.connections[canonical_name].execute("PRAGMA journal_mode=WAL;")  # Mejora concurrencia
            self.locks[canonical_name] = threading.Lock()

        return self.connections[canonical_name]

    def execute_query(self, db_name, query, params=()):
        """
        Ejecuta una consulta de escritura en la base de datos especificada.
        """
        normalized = self._normalize_db_name(db_name)
        conn = self.get_connection(db_name, _normalized=normalized)
        canonical_name, _ = normalized
        lock = self.locks[canonical_name]

        with lock:
            cursor = conn.cursor()
            try:
                cursor.execute(query, params)
                conn.commit()
                return cursor.lastrowid
            except sqlite3.Error as e:
                print(f"Error en la consulta: {e}")
                return None

    def fetch_query(self, db_name, query, params=()):
        """
        Ejecuta una consulta de lectura en la base de datos especificada.
        """
        normalized = self._normalize_db_name(db_name)
        conn = self.get_connection(db_name, _normalized=normalized)
        canonical_name, _ = normalized
        lock = self.locks[canonical_name]

        with lock:
            cursor = conn.cursor()
            try:
                cursor.execute(query, params)
                return cursor.fetchall()
            except sqlite3.Error as e:
                print(f"Error en la consulta: {e}")
                return None

    def close_connections(self):
        """
        Cierra todas las conexiones abiertas.
        """
        for db_name, conn in self.connections.items():
            conn.close()
        self.connections.clear()
        self.locks.clear()


if __name__ == "__main__":
    manager = DatabaseManager()
    manager.execute_query("test_db", "CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, action TEXT)")
    manager.execute_query("test_db", "INSERT INTO logs (action) VALUES (?)", ("Test de SQLitePlus",))
    print(manager.fetch_query("test_db", "SELECT * FROM logs"))
