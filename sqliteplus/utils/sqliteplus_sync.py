from __future__ import annotations

if __name__ == "__main__" and __package__ in {None, ""}:
    import sys
    from pathlib import Path
    from runpy import run_module

    package_root = Path(__file__).resolve().parents[2]
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    run_module("sqliteplus.utils.sqliteplus_sync", run_name="__main__")
    raise SystemExit()

import os
import sqlite3
import threading
from datetime import datetime
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

    def fetch_query_with_columns(self, query, params=()):
        """Devuelve el resultado de una consulta junto con los nombres de columna."""

        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(query, params)
                    rows = cursor.fetchall()
                    column_names = [col[0] for col in cursor.description or []]
                    return column_names, rows
                except sqlite3.Error as e:
                    raise SQLitePlusQueryError(query, e) from e

    def log_action(self, action):
        self.execute_query("INSERT INTO logs (action) VALUES (?)", (action,))

    def list_tables(self, include_views: bool = False, include_row_counts: bool = True):
        """Obtiene las tablas y vistas definidas en la base de datos."""

        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(
                        """
                        SELECT name, type
                        FROM sqlite_master
                        WHERE type IN ('table', 'view')
                          AND name NOT LIKE 'sqlite_%'
                        ORDER BY lower(name)
                        """
                    )
                    entries = cursor.fetchall()
                except sqlite3.Error as e:
                    raise SQLitePlusQueryError("LIST_TABLES", e) from e

                results = []
                for name, obj_type in entries:
                    if obj_type == "view" and not include_views:
                        continue

                    row_count = None
                    if include_row_counts and obj_type == "table":
                        identifier = name.replace('"', '""')
                        try:
                            count_cursor = conn.execute(f'SELECT COUNT(*) FROM "{identifier}"')
                            row_count = count_cursor.fetchone()[0]
                        except sqlite3.Error as e:
                            raise SQLitePlusQueryError(f"SELECT COUNT(*) FROM {name}", e) from e

                    results.append(
                        {
                            "name": name,
                            "type": obj_type,
                            "row_count": row_count,
                        }
                    )

                return results

    def describe_table(self, table_name: str):
        """Describe la estructura de una tabla, sus índices y claves foráneas."""

        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute("PRAGMA table_info(?)", (table_name,))
                    columns = cursor.fetchall()
                except sqlite3.Error as e:
                    raise SQLitePlusQueryError(f"PRAGMA table_info({table_name})", e) from e

                if not columns:
                    raise ValueError(f"La tabla '{table_name}' no existe en la base de datos actual.")

                try:
                    cursor.execute("PRAGMA index_list(?)", (table_name,))
                    indexes = cursor.fetchall()
                except sqlite3.Error as e:
                    raise SQLitePlusQueryError(f"PRAGMA index_list({table_name})", e) from e

                try:
                    cursor.execute("PRAGMA foreign_key_list(?)", (table_name,))
                    foreign_keys = cursor.fetchall()
                except sqlite3.Error as e:
                    raise SQLitePlusQueryError(f"PRAGMA foreign_key_list({table_name})", e) from e

                identifier = table_name.replace('"', '""')
                row_count = None
                try:
                    count_cursor = conn.execute(f'SELECT COUNT(*) FROM "{identifier}"')
                    row_count = count_cursor.fetchone()[0]
                except sqlite3.Error:
                    row_count = None

                return {
                    "row_count": row_count,
                    "columns": [
                        {
                            "cid": column[0],
                            "name": column[1],
                            "type": column[2],
                            "notnull": bool(column[3]),
                            "default": column[4],
                            "pk": bool(column[5]),
                        }
                        for column in columns
                    ],
                    "indexes": [
                        {
                            "seq": index[0],
                            "name": index[1],
                            "unique": bool(index[2]),
                            "origin": index[3],
                            "partial": bool(index[4]),
                        }
                        for index in indexes
                    ],
                    "foreign_keys": [
                        {
                            "id": fk[0],
                            "seq": fk[1],
                            "table": fk[2],
                            "from": fk[3],
                            "to": fk[4],
                            "on_update": fk[5],
                            "on_delete": fk[6],
                            "match": fk[7],
                        }
                        for fk in foreign_keys
                    ],
                }

    def get_database_statistics(self, include_views: bool = True):
        """Obtiene métricas generales de la base de datos."""

        tables = self.list_tables(include_views=include_views, include_row_counts=True)
        db_file = Path(self.db_path)
        size_in_bytes = db_file.stat().st_size if db_file.exists() else 0
        last_modified = (
            datetime.fromtimestamp(db_file.stat().st_mtime)
            if db_file.exists()
            else None
        )

        table_count = sum(1 for item in tables if item["type"] == "table")
        view_count = sum(1 for item in tables if item["type"] == "view")
        total_rows = sum((item["row_count"] or 0) for item in tables if item["row_count"] is not None)

        return {
            "path": self.db_path,
            "size_in_bytes": size_in_bytes,
            "last_modified": last_modified,
            "table_count": table_count,
            "view_count": view_count,
            "total_rows": total_rows,
        }


if __name__ == "__main__":
    db = SQLitePlus()
    db.log_action("Inicialización del sistema")
    print("SQLitePlus está listo para usar.")
