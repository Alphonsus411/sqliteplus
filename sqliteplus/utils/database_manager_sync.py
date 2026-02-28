from __future__ import annotations

import logging
import os
import sqlite3
import threading
from pathlib import Path

from sqliteplus.utils.crypto_sqlite import (
    apply_cipher_key,
    SQLitePlusCipherError,
)

logger = logging.getLogger(__name__)


class DatabaseQueryError(Exception):
    """Excepción personalizada para errores en consultas SQL."""

    def __init__(self, query: str, original_error: Exception):
        self.query = query
        self.original_error = original_error
        super().__init__(f"Error al ejecutar la consulta '{query}': {original_error}")


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    normalized = value.strip().lower()
    if not normalized:
        return False
    return normalized not in {"0", "false", "no", "off"}


class DatabaseManager:
    """
    Gestor de bases de datos SQLite que maneja múltiples bases en paralelo
    y soporta concurrencia con `threading` y cifrado con SQLCipher.
    """

    def __init__(
        self,
        base_dir="databases",
        require_encryption: bool | None = None,
    ):
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)  # Asegura que el directorio exista
        self.connections = {}  # Diccionario de conexiones a bases de datos
        self.locks = {}  # Bloqueos para manejar concurrencia en cada base de datos

        if require_encryption is None:
            self.require_encryption = os.getenv("SQLITE_DB_KEY") is not None
        else:
            self.require_encryption = require_encryption

    def _normalize_db_name(self, raw_name: str) -> tuple[str, Path]:
        sanitized = raw_name.strip()
        if not sanitized:
            raise ValueError("Nombre de base de datos inválido")

        if any(token in sanitized for token in ("..", "/", "\\")):
            raise ValueError("Nombre de base de datos inválido")

        file_name = sanitized if sanitized.lower().endswith(".db") else f"{sanitized}.db"
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
            # Obtener y validar clave de cifrado
            raw_encryption_key = os.getenv("SQLITE_DB_KEY")
            if raw_encryption_key is not None and raw_encryption_key.strip() == "":
                encryption_key = ""
            else:
                encryption_key = raw_encryption_key

            if encryption_key == "" and not self.require_encryption:
                encryption_key = None

            if self.require_encryption and (encryption_key is None or encryption_key == ""):
                logger.error(
                    "Clave de cifrado ausente o vacía en la variable de entorno 'SQLITE_DB_KEY'"
                )
                raise SQLitePlusCipherError(
                    message="La clave de cifrado es obligatoria y no puede estar vacía"
                )

            # Crear conexión
            try:
                conn = sqlite3.connect(str(db_path), check_same_thread=False)
                apply_cipher_key(conn, encryption_key)
                conn.execute("PRAGMA journal_mode=WAL;")  # Mejora concurrencia
                self.connections[canonical_name] = conn
                self.locks[canonical_name] = threading.Lock()
            except (sqlite3.Error, SQLitePlusCipherError) as exc:
                logger.error("Error al conectar con la base de datos '%s'", canonical_name, exc_info=exc)
                raise

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
            except sqlite3.Error as exc:
                logger.error("Error en consulta de escritura", exc_info=exc)
                raise DatabaseQueryError(query, exc) from exc

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
            except sqlite3.Error as exc:
                logger.error("Error en consulta de lectura", exc_info=exc)
                raise DatabaseQueryError(query, exc) from exc

    def fetch_query_with_columns(self, db_name, query, params=()):
        """Ejecuta una consulta de lectura y retorna también los nombres de columna."""
        normalized = self._normalize_db_name(db_name)
        conn = self.get_connection(db_name, _normalized=normalized)
        canonical_name, _ = normalized
        lock = self.locks[canonical_name]

        with lock:
            cursor = conn.cursor()
            try:
                cursor.execute(query, params)
                rows = cursor.fetchall()
                column_names = [col[0] for col in cursor.description or []]
                return column_names, rows
            except sqlite3.Error as exc:
                logger.error("Error en consulta de lectura con columnas", exc_info=exc)
                raise DatabaseQueryError(query, exc) from exc

    def close_connections(self):
        """
        Cierra todas las conexiones abiertas.
        """
        for db_name, conn in self.connections.items():
            try:
                conn.close()
            except sqlite3.Error:
                pass
        self.connections.clear()
        self.locks.clear()


def main() -> int:
    """Punto de entrada de demostración para DatabaseManager."""

    manager = DatabaseManager()
    manager.execute_query("test_db", "CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, action TEXT)")
    manager.execute_query("test_db", "INSERT INTO logs (action) VALUES (?)", ("Test de SQLitePlus Sync",))
    rows = manager.fetch_query("test_db", "SELECT * FROM logs")
    print(f"Entradas registradas: {len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
