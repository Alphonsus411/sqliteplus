from __future__ import annotations

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    _current_path = Path(__file__).resolve()
    for parent in _current_path.parents:
        if parent.name == "sqliteplus":
            project_root = parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            break

import csv
import os
import shutil
import sqlite3
from pathlib import Path

from sqliteplus.utils.constants import DEFAULT_DB_PATH, resolve_default_db_path
from sqliteplus.utils.sqliteplus_sync import apply_cipher_key, SQLitePlusCipherError


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
            resolved_path = resolve_default_db_path()
        else:
            raw_path = Path(db_path)
            if raw_path == Path(DEFAULT_DB_PATH):
                resolved_path = resolve_default_db_path(prefer_package=False)
            else:
                resolved_path = raw_path
        self.db_path = str(resolved_path)
        self.backup_dir = backup_dir
        self.cipher_key = cipher_key if cipher_key is not None else os.getenv("SQLITE_DB_KEY")
        os.makedirs(self.backup_dir, exist_ok=True)

    def export_to_csv(self, table_name: str, output_file: str):
        """
        Exporta los datos de una tabla a un archivo CSV.
        """
        if not self._is_valid_table_name(table_name):
            raise ValueError(f"Nombre de tabla inválido: {table_name}")

        query = f"SELECT * FROM {self._escape_identifier(table_name)}"

        try:
            with sqlite3.connect(self.db_path) as conn:
                apply_cipher_key(conn, self.cipher_key)
                cursor = conn.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                column_names = [desc[0] for desc in cursor.description]

            with open(output_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(column_names)
                writer.writerows(rows)

            print(f"Datos exportados correctamente a {output_file}")
        except SQLitePlusCipherError as exc:
            raise RuntimeError(str(exc)) from exc
        except sqlite3.Error as e:
            raise sqlite3.Error(f"Error al exportar datos: {e}") from e

    def backup_database(self):
        """
        Crea una copia de seguridad de la base de datos.
        """
        backup_file = os.path.join(self.backup_dir, f"backup_{self._get_timestamp()}.db")
        try:
            if not os.path.exists(self.db_path):
                raise FileNotFoundError(
                    f"No se encontró la base de datos origen: {self.db_path}"
                )

            os.makedirs(os.path.dirname(backup_file), exist_ok=True)

            with sqlite3.connect(self.db_path) as source_conn:
                apply_cipher_key(source_conn, self.cipher_key)
                with sqlite3.connect(backup_file) as backup_conn:
                    apply_cipher_key(backup_conn, self.cipher_key)
                    source_conn.backup(backup_conn)

            self._copy_wal_and_shm(self.db_path, backup_file)

            print(f"Copia de seguridad creada en {backup_file}")
            return backup_file
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

            target_dir = os.path.dirname(target_db_path)
            if target_dir:
                os.makedirs(target_dir, exist_ok=True)

            with sqlite3.connect(self.db_path) as source_conn:
                apply_cipher_key(source_conn, self.cipher_key)
                with sqlite3.connect(target_db_path) as target_conn:
                    apply_cipher_key(target_conn, self.cipher_key)
                    source_conn.backup(target_conn)

            self._copy_wal_and_shm(self.db_path, target_db_path)

            print(f"Base de datos replicada en {target_db_path}")
            return target_db_path
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
        return bool(table_name) and table_name.isidentifier()

    @staticmethod
    def _escape_identifier(identifier: str) -> str:
        escaped_identifier = identifier.replace('"', '""')
        return f'"{escaped_identifier}"'

    @staticmethod
    def _copy_wal_and_shm(source_path: str, target_path: str):
        """Replica los archivos WAL y SHM asociados cuando existen."""
        base_source = source_path
        base_target = target_path
        copied_files = []
        for suffix in ("-wal", "-shm"):
            src_file = f"{base_source}{suffix}"
            if os.path.exists(src_file):
                dest_file = f"{base_target}{suffix}"
                if os.path.exists(dest_file):
                    os.remove(dest_file)
                shutil.copy2(src_file, dest_file)
                copied_files.append(dest_file)
        return copied_files


if __name__ == "__main__":
    replicator = SQLiteReplication()
    replicator.backup_database()
    replicator.export_to_csv("logs", "logs_export.csv")
