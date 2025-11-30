# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cdivision=True
"""Implementación acelerada de replicación y exportación SQLite."""

from __future__ import annotations

cimport cython
from cpython.size_t cimport Py_ssize_t

import csv
import logging
import os
import shutil
import sqlite3
import sys
from pathlib import Path

from sqliteplus.core.schemas import is_valid_sqlite_identifier
from sqliteplus.utils.constants import (
    DEFAULT_DB_PATH,
    PACKAGE_DB_PATH,
    resolve_default_db_path,
)
from sqliteplus.utils.sqliteplus_sync cimport apply_cipher_key, SQLitePlusCipherError

logger = logging.getLogger(__name__)

__all__ = ["SQLiteReplication", "PACKAGE_DB_PATH", "DEFAULT_DB_PATH"]


@cython.cfunc
def _package_db_path() -> Path:
    wrapper = sys.modules.get("sqliteplus.utils.replication_sync")
    candidate = getattr(wrapper, "PACKAGE_DB_PATH", PACKAGE_DB_PATH)
    return Path(candidate)


cdef class SQLiteReplication:
    """Módulo para exportación y replicación de bases de datos SQLitePlus."""

    cdef public str db_path
    cdef public object backup_dir
    cdef public object cipher_key

    def __cinit__(
        self,
        db_path: str | os.PathLike[str] | None = None,
        backup_dir="backups",
        cipher_key: str | None = None,
    ):
        cdef Path resolved_path
        if db_path is None:
            resolved_path = resolve_default_db_path(prefer_package=False)
        else:
            resolved_path = Path(db_path).expanduser()
            if resolved_path == Path(DEFAULT_DB_PATH):
                resolved_path = resolve_default_db_path(prefer_package=False)

        resolved_path = resolved_path.expanduser().resolve()
        resolved_path = self._select_writable_path(resolved_path)
        self.db_path = str(resolved_path)

        self.backup_dir = Path(backup_dir).expanduser().resolve()
        self.cipher_key = cipher_key if cipher_key is not None else os.getenv("SQLITE_DB_KEY")
        (<Path>self.backup_dir).mkdir(parents=True, exist_ok=True)

    def export_to_csv(self, str table_name, str output_file, bint overwrite=False):
        """Exporta los datos de una tabla a un archivo CSV."""
        if not self._is_valid_table_name(table_name):
            raise ValueError(f"Nombre de tabla inválido: {table_name}")

        cdef Path db_path = Path(self.db_path)
        if not db_path.exists():
            raise FileNotFoundError(
                f"No se encontró la base de datos origen: {self.db_path}"
            )

        cdef str query = f"SELECT * FROM {self._escape_identifier(table_name)}"
        cdef Path output_path = Path(output_file).expanduser().resolve()

        if output_path.exists() and not overwrite:
            raise FileExistsError(
                f"El archivo de salida ya existe: {output_path}. Usa --overwrite para reemplazarlo."
            )

        try:
            with sqlite3.connect(self.db_path) as conn:
                apply_cipher_key(conn, self.cipher_key)
                cursor = conn.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                description = cursor.description

            output_path.parent.mkdir(parents=True, exist_ok=True)

            with output_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                cdef Py_ssize_t col_count = len(description)
                cdef list column_names = [description[idx][0] for idx in range(col_count)]
                writer.writerow(column_names)

                cdef Py_ssize_t row_count = len(rows)
                cdef Py_ssize_t row_idx
                for row_idx in range(row_count):
                    writer.writerow(rows[row_idx])

            logger.info("Datos exportados correctamente a %s", output_path)
            return str(output_path)
        except SQLitePlusCipherError as exc:
            raise RuntimeError(str(exc)) from exc
        except FileNotFoundError:
            raise
        except sqlite3.Error as e:
            raise sqlite3.Error(f"Error al exportar datos: {e}") from e

    def backup_database(self):
        """Crea una copia de seguridad de la base de datos."""
        cdef Path backup_file = (<Path>self.backup_dir) / f"backup_{self._get_timestamp()}.db"
        try:
            if not os.path.exists(self.db_path):
                raise FileNotFoundError(
                    f"No se encontró la base de datos origen: {self.db_path}"
                )

            with sqlite3.connect(self.db_path) as source_conn:
                apply_cipher_key(source_conn, self.cipher_key)
                with sqlite3.connect(str(backup_file)) as backup_conn:
                    apply_cipher_key(backup_conn, self.cipher_key)
                    source_conn.backup(backup_conn)

            self._copy_wal_and_shm(self.db_path, backup_file)

            logger.info("Copia de seguridad creada en %s", backup_file)
            return str(backup_file)
        except SQLitePlusCipherError as exc:
            raise RuntimeError(str(exc)) from exc
        except Exception as e:
            raise RuntimeError(
                f"Error al realizar la copia de seguridad: {e}"
            ) from e

    def replicate_database(self, str target_db_path):
        """Replica la base de datos en otra ubicación."""
        try:
            if not os.path.exists(self.db_path):
                raise FileNotFoundError(
                    f"No se encontró la base de datos origen: {self.db_path}"
                )

            cdef Path target_path = Path(target_db_path).expanduser().resolve()
            cdef Path target_dir = target_path.parent
            if target_dir:
                target_dir.mkdir(parents=True, exist_ok=True)

            with sqlite3.connect(self.db_path) as source_conn:
                apply_cipher_key(source_conn, self.cipher_key)
                with sqlite3.connect(str(target_path)) as target_conn:
                    apply_cipher_key(target_conn, self.cipher_key)
                    source_conn.backup(target_conn)

            self._copy_wal_and_shm(self.db_path, target_path)

            logger.info("Base de datos replicada en %s", target_path)
            return str(target_path)
        except SQLitePlusCipherError as exc:
            raise RuntimeError(str(exc)) from exc
        except Exception as e:
            raise RuntimeError(f"Error en la replicación: {e}") from e

    def _get_timestamp(self):
        """Genera un timestamp para los nombres de archivo."""
        import datetime
        return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    @cython.cfunc
    @cython.locals(table_name=object, sanitized=str)
    def _is_valid_table_name(self, table_name) -> cython.bint:
        if not isinstance(table_name, str):
            return False

        sanitized = (<str>table_name).strip()
        return bool(sanitized) and is_valid_sqlite_identifier(sanitized)

    def _escape_identifier(self, str identifier) -> str:
        cdef str sanitized = identifier.strip()
        cdef str escaped_identifier = sanitized.replace('"', '""')
        return f'"{escaped_identifier}"'

    def _copy_wal_and_shm(
        self,
        source_path: str | os.PathLike[str],
        target_path: str | os.PathLike[str],
    ) -> list[str]:
        """Replica los archivos WAL y SHM asociados cuando existen."""

        cdef Path base_source = Path(source_path)
        cdef Path base_target = Path(target_path)
        cdef list copied_files = []
        cdef str suffix
        cdef Py_ssize_t read_bytes
        buf = bytearray(1024 * 1024)
        mv = memoryview(buf)

        for suffix in ("-wal", "-shm"):
            src_file = base_source.with_name(base_source.name + suffix)
            if src_file.exists():
                dest_file = base_target.with_name(base_target.name + suffix)
                if dest_file.exists():
                    dest_file.unlink()
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                with src_file.open("rb") as src, dest_file.open("wb") as dest:
                    while True:
                        read_bytes = src.readinto(buf)
                        if read_bytes == 0:
                            break
                        dest.write(mv[:read_bytes])
                shutil.copystat(src_file, dest_file, follow_symlinks=True)
                copied_files.append(str(dest_file))

        return copied_files

    def _default_local_db(self) -> Path:
        return (Path.cwd() / Path(DEFAULT_DB_PATH)).resolve()

    def _select_writable_path(self, Path candidate):
        cdef Path local_default = self._default_local_db()

        requires_local_copy = self._is_inside_package(candidate) or not self._can_write_to(
            candidate.parent
        )

        if requires_local_copy:
            logger.warning(
                "La ruta %s no es segura para escritura. Se utilizará %s en su lugar.",
                candidate,
                local_default,
            )
            self._copy_database_to_local(candidate, local_default)
            candidate = local_default

        if candidate == local_default:
            self._ensure_local_database(candidate)

        return candidate

    def _copy_database_to_local(self, Path source, Path destination) -> None:
        """Replica la base de datos origen y sus archivos asociados al directorio local."""

        if not source.exists():
            raise FileNotFoundError(
                f"No se pudo copiar la base de datos {source}: el archivo no existe"
            )

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        self._copy_wal_and_shm(source, destination)

    def _is_inside_package(self, Path path) -> cython.bint:
        package_root = _package_db_path().parent.parent
        try:
            path.relative_to(package_root)
        except ValueError:
            return False
        return True

    def _can_write_to(self, Path directory) -> cython.bint:
        probe = directory
        while probe and not probe.exists():
            parent = probe.parent
            if parent == probe:
                break
            probe = parent

        return os.access(probe, os.W_OK)

    def _ensure_local_database(self, Path target) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.touch()
