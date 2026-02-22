# cython: language_level=3

import os
import sqlite3
import threading
from datetime import datetime
from pathlib import Path

from sqliteplus.core.schemas import is_valid_sqlite_identifier
from sqliteplus.utils.constants import DEFAULT_DB_PATH, resolve_default_db_path

cdef public tuple SQLITEPLUS_PUBLIC_API = (
    "SQLitePlus",
    "SQLitePlusCipherError",
    "SQLitePlusQueryError",
    "apply_cipher_key",
)
__all__ = SQLITEPLUS_PUBLIC_API


class SQLitePlusQueryError(RuntimeError):
    """Excepción personalizada para errores en consultas SQL."""

    def __init__(self, query, original_exception):
        self.query = query
        self.original_exception = original_exception
        message = f"Error al ejecutar la consulta SQL '{query}': {original_exception}"
        super().__init__(message)


class SQLitePlusCipherError(RuntimeError):
    """Excepción para errores al aplicar la clave SQLCipher."""

    def __init__(self, original_exception):
        self.original_exception = original_exception
        message = (
            "No se pudo aplicar la clave SQLCipher. Asegúrate de que tu intérprete "
            "de SQLite tiene soporte para SQLCipher antes de continuar."
        )
        super().__init__(message)


cpdef void apply_cipher_key(object connection, object cipher_key):
    """Aplica la clave de cifrado a una conexión abierta."""
    if not cipher_key:
        return

    cdef str escaped_key = (<str>cipher_key).replace("'", "''")
    cdef bytes encoded_key = escaped_key.encode("utf-8")
    cdef const char* encoded_key_ptr = encoded_key
    cdef int encoded_length = len(encoded_key)
    if encoded_length == 0 or encoded_key_ptr is NULL:
        return

    try:
        connection.execute(f"PRAGMA key = '{escaped_key}';")
    except sqlite3.DatabaseError as exc:  # pragma: no cover - depende de SQLCipher
        raise SQLitePlusCipherError(exc) from exc


cdef class SQLitePlus:
    """Manejador de SQLite con soporte para cifrado y concurrencia."""

    def __init__(
        self,
        db_path: str | os.PathLike[str] = DEFAULT_DB_PATH,
        cipher_key: str | None = None,
    ):
        raw_path = Path(db_path).expanduser()
        if raw_path == Path(DEFAULT_DB_PATH):
            resolved_db_path = resolve_default_db_path(prefer_package=False)
        else:
            resolved_db_path = raw_path

        normalized_path = Path(resolved_db_path).expanduser().resolve()
        self.db_path = str(normalized_path)
        self.cipher_key = cipher_key if cipher_key is not None else os.getenv("SQLITE_DB_KEY")
        directory = os.path.dirname(self.db_path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        self.lock = threading.Lock()
        self._initialize_db()

    cdef void _initialize_db(self):
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

    cpdef object get_connection(self):
        conn = sqlite3.connect(self.db_path, check_same_thread=False)
        try:
            apply_cipher_key(conn, self.cipher_key)
            conn.execute("PRAGMA journal_mode=WAL;")
        except SQLitePlusCipherError:
            conn.close()
            raise
        except sqlite3.Error as exc:
            conn.close()
            raise SQLitePlusQueryError("PRAGMA journal_mode=WAL", exc) from exc
        return conn

    cpdef object execute_query(self, query, params=()):
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(query, params)
                    conn.commit()
                    return cursor.lastrowid
                except sqlite3.Error as e:
                    raise SQLitePlusQueryError(query, e) from e

    cpdef object fetch_query(self, query, params=()):
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(query, params)
                    return cursor.fetchall()
                except sqlite3.Error as e:
                    raise SQLitePlusQueryError(query, e) from e

    cpdef object fetch_query_with_columns(self, query, params=()):
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

    cpdef object log_action(self, action):
        return self.execute_query("INSERT INTO logs (action) VALUES (?)", (action,))

    cpdef object list_tables(self, bint include_views=False, bint include_row_counts=True):
        """Obtiene las tablas y vistas definidas en la base de datos."""
        cdef int idx
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
                for idx in range(len(entries)):
                    name, obj_type = entries[idx]
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

    cpdef str _escape_identifier(self, str table_name):
        sanitized = table_name.strip()
        if not sanitized:
            raise ValueError("El nombre de la tabla no puede estar vacío.")

        if not is_valid_sqlite_identifier(sanitized):
            raise ValueError(
                (
                    f"Nombre de tabla inválido: '{table_name}'."
                    " Evita comillas dobles, caracteres de control y"
                    " espacios al inicio o al final."
                )
            )

        return sanitized.replace('"', '""')

    cpdef object describe_table(self, str table_name):
        """Describe la estructura de una tabla, sus índices y claves foráneas."""

        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                escaped_name = self._escape_identifier(table_name)
                quoted_name = f'"{escaped_name}"'

                try:
                    cursor.execute(f"PRAGMA table_info({quoted_name})")
                    columns = cursor.fetchall()
                except sqlite3.Error as e:
                    raise SQLitePlusQueryError(f"PRAGMA table_info({table_name})", e) from e

                if not columns:
                    raise ValueError(f"La tabla '{table_name}' no existe en la base de datos actual.")

                try:
                    cursor.execute(f"PRAGMA index_list({quoted_name})")
                    indexes = cursor.fetchall()
                except sqlite3.Error as e:
                    raise SQLitePlusQueryError(f"PRAGMA index_list({table_name})", e) from e

                try:
                    cursor.execute(f"PRAGMA foreign_key_list({quoted_name})")
                    foreign_keys = cursor.fetchall()
                except sqlite3.Error as e:
                    raise SQLitePlusQueryError(f"PRAGMA foreign_key_list({table_name})", e) from e

                identifier = escaped_name
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

    cpdef object get_database_statistics(self, bint include_views=True):
        """Obtiene métricas generales de la base de datos."""

        tables = self.list_tables(include_views=include_views, include_row_counts=True)
        db_file = Path(self.db_path)
        try:
            stat_result = db_file.stat()
        except FileNotFoundError:
            stat_result = None

        size_in_bytes = stat_result.st_size if stat_result else 0
        last_modified = (
            datetime.fromtimestamp(stat_result.st_mtime)
            if stat_result
            else None
        )

        cdef int table_count = 0
        cdef int view_count = 0
        cdef int idx
        cdef int total_rows = 0

        for idx in range(len(tables)):
            item = tables[idx]
            if item["type"] == "table":
                table_count += 1
            elif item["type"] == "view":
                view_count += 1

            if item.get("row_count") is not None:
                total_rows += item.get("row_count") or 0

        return {
            "path": self.db_path,
            "size_in_bytes": size_in_bytes,
            "last_modified": last_modified,
            "table_count": table_count,
            "view_count": view_count,
            "total_rows": total_rows,
        }
