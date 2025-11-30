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

import importlib.machinery
import importlib.util
import os
import sqlite3
import sys
from pathlib import Path
from types import ModuleType

from sqliteplus.utils.constants import DEFAULT_DB_PATH, PACKAGE_DB_PATH
from sqliteplus.utils.sqliteplus_sync import apply_cipher_key

__all__ = ["SQLiteReplication", "PACKAGE_DB_PATH", "DEFAULT_DB_PATH"]


def _load_cython_variant() -> ModuleType | None:
    """Carga el módulo C si está disponible junto a este archivo."""

    if __name__ == "__main__":
        return None

    module_path = Path(__file__)
    for suffix in importlib.machinery.EXTENSION_SUFFIXES:
        candidate = module_path.with_suffix(suffix)
        if candidate.exists():
            spec = importlib.util.spec_from_file_location(__name__, candidate)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[__name__] = module
                spec.loader.exec_module(module)
                return module
    return None


_cython_module = _load_cython_variant()
if _cython_module is not None:
    globals().update(_cython_module.__dict__)
else:
    from sqliteplus.utils._replication_sync_py import *


def _ensure_demo_database(db_path: Path, cipher_key: str | None) -> None:
    """Crea una base de datos mínima con una tabla ``logs`` si no existe."""

    db_path.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(db_path) as connection:
        apply_cipher_key(connection, cipher_key)
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                message TEXT NOT NULL,
                created_at TEXT DEFAULT (datetime('now'))
            )
            """
        )
        cursor = connection.execute("SELECT COUNT(*) FROM logs")
        has_rows = cursor.fetchone()[0] > 0
        if not has_rows:
            connection.executemany(
                "INSERT INTO logs (message) VALUES (?)",
                [("Registro inicial",), ("Segundo registro",)],
            )


def main() -> int:
    """Ejecuta una replicación de demostración desde cualquier ruta."""

    cipher_key = os.getenv("SQLITE_DB_KEY")
    db_path = Path(DEFAULT_DB_PATH).expanduser().resolve()

    _ensure_demo_database(db_path, cipher_key)

    replicator = SQLiteReplication(db_path=db_path, cipher_key=cipher_key)
    backup_path = replicator.backup_database()

    export_target = Path.cwd() / "logs_export.csv"
    replicator.export_to_csv("logs", str(export_target), overwrite=True)

    print(f"Base de datos de demostración disponible en {db_path}")
    print(f"Copia de seguridad creada en: {backup_path}")
    print(f"Exportación CSV generada en: {export_target}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
