from __future__ import annotations

if __name__ == "__main__" and __package__ in {None, ""}:
    import sys
    from pathlib import Path
    from runpy import run_module

    package_root = Path(__file__).resolve().parents[2]
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    run_module("sqliteplus.utils.replication_sync", run_name="__main__")
    raise SystemExit()

import csv
import logging
import os
import shutil
import sqlite3
from pathlib import Path

from sqliteplus.core.schemas import is_valid_sqlite_identifier
from sqliteplus.utils.constants import (
    DEFAULT_DB_PATH,
    PACKAGE_DB_PATH,
    resolve_default_db_path,
)
from sqliteplus.utils.sqliteplus_sync import apply_cipher_key, SQLitePlusCipherError


logger = logging.getLogger(__name__)


class SQLiteReplication:
    """
    Módulo para exportación y replicación de bases de datos SQLitePlus.
    """

    def __init__(
        self,
        db_path: str | os.PathLike[str] | None = None,
        backup_dir="backups",
        cipher_key: str | None = None,
    ):
        if db_path is None:
            resolved_path = resolve_default_db_path(prefer_package=False)
        else:
            raw_path = Path(db_path).expanduser()
            if raw_path == Path(DEFAULT_DB_PATH):
                resolved_path = resolve_default_db_path(prefer_package=False)
            else:
                resolved_path = raw_path

        normalized_db_path = Path(resolved_path).expanduser().resolve()
        normalized_db_path = self._select_writable_path(normalized_db_path)
        self.db_path = str(normalized_db_path)

        backup_base = Path(backup_dir).expanduser().resolve()
        self.backup_dir = backup_base
        self.cipher_key = cipher_key if cipher_key is not None else os.getenv("SQLITE_DB_KEY")
        self.backup_dir.mkdir(parents=True, exist_ok=True)

    def export_to_csv(self, table_name: str, output_file: str):
        """
        Exporta los datos de una tabla a un archivo CSV.
        """
        if not self._is_valid_table_name(table_name):
            raise ValueError(f"Nombre de tabla inválido: {table_name}")

        if not Path(self.db_path).exists():
            raise FileNotFoundError(
                f"No se encontró la base de datos origen: {self.db_path}"
            )

        query = f"SELECT * FROM {self._escape_identifier(table_name)}"

        output_path = Path(output_file).expanduser().resolve()

        try:
            with sqlite3.connect(self.db_path) as conn:
                apply_cipher_key(conn, self.cipher_key)
                cursor = conn.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                column_names = [desc[0] for desc in cursor.description]

            output_path.parent.mkdir(parents=True, exist_ok=True)

            with output_path.open("w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(column_names)
                writer.writerows(rows)

            logger.info("Datos exportados correctamente a %s", output_path)
            return str(output_path)
        except SQLitePlusCipherError as exc:
            raise RuntimeError(str(exc)) from exc
        except FileNotFoundError:
            raise
        except sqlite3.Error as e:
            raise sqlite3.Error(f"Error al exportar datos: {e}") from e

    def backup_database(self):
        """
        Crea una copia de seguridad de la base de datos.
        """
        backup_file = self.backup_dir / f"backup_{self._get_timestamp()}.db"
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

    def replicate_database(self, target_db_path: str):
        """
        Replica la base de datos en otra ubicación.
        """
        try:
            if not os.path.exists(self.db_path):
                raise FileNotFoundError(
                    f"No se encontró la base de datos origen: {self.db_path}"
                )

            target_path = Path(target_db_path).expanduser().resolve()
            target_dir = target_path.parent
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
        """
        Genera un timestamp para los nombres de archivo.
        """
        import datetime
        return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    @staticmethod
    def _is_valid_table_name(table_name: str) -> bool:
        if not isinstance(table_name, str):
            return False

        sanitized = table_name.strip()
        return bool(sanitized) and is_valid_sqlite_identifier(sanitized)

    @staticmethod
    def _escape_identifier(identifier: str) -> str:
        sanitized = identifier.strip()
        escaped_identifier = sanitized.replace('"', '""')
        return f'"{escaped_identifier}"'

    @staticmethod
    def _copy_wal_and_shm(
        source_path: str | os.PathLike[str],
        target_path: str | os.PathLike[str],
    ) -> list[str]:
        """Replica los archivos WAL y SHM asociados cuando existen."""

        base_source = Path(source_path)
        base_target = Path(target_path)
        copied_files: list[str] = []

        for suffix in ("-wal", "-shm"):
            src_file = base_source.with_name(base_source.name + suffix)
            if src_file.exists():
                dest_file = base_target.with_name(base_target.name + suffix)
                if dest_file.exists():
                    dest_file.unlink()
                dest_file.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_file, dest_file)
                copied_files.append(str(dest_file))

        return copied_files

    @staticmethod
    def _default_local_db() -> Path:
        return (Path.cwd() / Path(DEFAULT_DB_PATH)).resolve()

    def _select_writable_path(self, candidate: Path) -> Path:
        local_default = self._default_local_db()

        redirected_from: Path | None = None

        if self._is_inside_package(candidate) or not self._can_write_to(candidate.parent):
            logger.warning(
                "La ruta %s no es segura para escritura. Se utilizará %s en su lugar.",
                candidate,
                local_default,
            )
            redirected_from = candidate
            candidate = local_default

        if redirected_from is not None:
            if redirected_from != candidate:
                self._copy_to_local_database(redirected_from, candidate)
            else:
                self._ensure_local_database(candidate)
        elif candidate == local_default:
            self._ensure_local_database(candidate)

        return candidate

    @staticmethod
    def _is_inside_package(path: Path) -> bool:
        package_root = PACKAGE_DB_PATH.parent.parent
        try:
            path.relative_to(package_root)
        except ValueError:
            return False
        return True

    @staticmethod
    def _can_write_to(directory: Path) -> bool:
        probe = directory
        while probe and not probe.exists():
            parent = probe.parent
            if parent == probe:
                break
            probe = parent

        return os.access(probe, os.W_OK)

    @staticmethod
    def _ensure_local_database(target: Path) -> None:
        target.parent.mkdir(parents=True, exist_ok=True)
        if not target.exists():
            target.touch()

    @classmethod
    def _copy_to_local_database(cls, source: Path, destination: Path) -> None:
        if not source.exists():
            raise FileNotFoundError(f"No se encontró la base de datos origen: {source}")

        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
        cls._copy_wal_and_shm(source, destination)


if __name__ == "__main__":
    # Crear la base de datos por defecto si aún no existe antes de iniciar las
    # tareas de replicación.  Cuando el script se ejecuta fuera del árbol del
    # proyecto (por ejemplo, desde un directorio temporal) el archivo de base
    # de datos aún no ha sido creado y las operaciones de copia fallan con un
    # FileNotFoundError.  Inicializamos SQLitePlus para generar la estructura
    # necesaria y así garantizar que los comandos posteriores funcionen.
    from sqliteplus.utils.sqliteplus_sync import SQLitePlus

    database = SQLitePlus()
    database.log_action("Inicialización de replicación desde script")

    replicator = SQLiteReplication(db_path=database.db_path)
    replicator.backup_database()
    replicator.export_to_csv("logs", "logs_export.csv")
