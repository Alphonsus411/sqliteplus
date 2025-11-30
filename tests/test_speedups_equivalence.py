import sqlite3
from pathlib import Path

import pytest


def _prepare_database(db_path: Path) -> None:
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            """
            CREATE TABLE IF NOT EXISTS items (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                price REAL DEFAULT 0.0
            )
            """
        )
        conn.execute(
            """
            CREATE VIEW IF NOT EXISTS items_view AS
            SELECT name, price FROM items
            """
        )
        conn.executemany(
            "INSERT INTO items (name, price) VALUES (?, ?)",
            [("alpha", 1.0), ("beta", 2.0), ("gamma", 3.5)],
        )


def test_schema_speedups_match_python_impl(speedup_variants):
    cython_schemas, _, _ = speedup_variants(force_fallback=False)
    fallback_schemas, _, _ = speedup_variants(force_fallback=True)

    columns = {
        " id ": "integer primary key autoincrement",
        "Nombre": " text not null",
        "precio": " real default 0.0",
    }
    assert (
        cython_schemas._normalize_columns_impl(columns)
        == fallback_schemas._normalize_columns_impl(columns)
    )

    expressions = ["now()", "(1+2)", "TRIM( nombre )", "'texto'"]
    for expr in expressions:
        assert cython_schemas._parse_function_call_impl(expr) == fallback_schemas._py_parse_function_call(expr)

    candidates = ["tabla1", "_tabla2", "invalida tabla", "otra;tabla"]
    for name in candidates:
        assert cython_schemas.is_valid_sqlite_identifier(name) == fallback_schemas._py_is_valid_sqlite_identifier(name)


def test_sqliteplus_sync_consistency_across_variants(speedup_variants, tmp_path):
    cython_schemas, cython_sync, _ = speedup_variants(force_fallback=False)
    _, fallback_sync, _ = speedup_variants(force_fallback=True)

    db_path = tmp_path / "consistency.db"
    _prepare_database(db_path)

    cython_client = cython_sync.SQLitePlus(db_path=db_path)
    fallback_client = fallback_sync.SQLitePlus(db_path=db_path)

    assert cython_client.list_tables(include_views=True, include_row_counts=False) == fallback_client.list_tables(include_views=True, include_row_counts=False)

    with pytest.raises(ValueError):
        cython_client._escape_identifier("tabla;invalida")
    with pytest.raises(ValueError):
        fallback_client._escape_identifier("tabla;invalida")


def test_sqliteplus_execute_and_fetch_equivalence(speedup_variants, tmp_path):
    _, cython_sync, _ = speedup_variants(force_fallback=False)
    _, fallback_sync, _ = speedup_variants(force_fallback=True)

    def run_workflow(sync_module, db_path):
        client = sync_module.SQLitePlus(db_path=db_path)
        inserted_ids = [
            client.execute_query("INSERT INTO logs (action) VALUES (?)", ("alpha",)),
            client.execute_query("INSERT INTO logs (action) VALUES (?)", ("beta",)),
            client.execute_query("INSERT INTO logs (action) VALUES (?)", ("gamma",)),
        ]
        rows = client.fetch_query("SELECT id, action FROM logs ORDER BY id")
        return inserted_ids, rows

    cython_ids, cython_rows = run_workflow(cython_sync, tmp_path / "cython.sqlite")
    fallback_ids, fallback_rows = run_workflow(fallback_sync, tmp_path / "fallback.sqlite")

    assert cython_rows == fallback_rows
    assert cython_ids == fallback_ids


def test_replication_exports_identical_results(speedup_variants, tmp_path):
    _, cython_sync, cython_replication = speedup_variants(force_fallback=False)
    _, fallback_sync, fallback_replication = speedup_variants(force_fallback=True)

    db_path = tmp_path / "replication.db"
    _prepare_database(db_path)

    cython_export = tmp_path / "cython.csv"
    fallback_export = tmp_path / "fallback.csv"

    cython_replication.SQLiteReplication(db_path=db_path, backup_dir=tmp_path / "cython_backups").export_to_csv(
        "items", str(cython_export), overwrite=True
    )
    fallback_replication.SQLiteReplication(db_path=db_path, backup_dir=tmp_path / "fallback_backups").export_to_csv(
        "items", str(fallback_export), overwrite=True
    )

    assert cython_export.read_text(encoding="utf-8") == fallback_export.read_text(encoding="utf-8")

    with cython_sync.sqlite3.connect(db_path) as conn:
        conn.execute("INSERT INTO items (name, price) VALUES ('delta', 4.2)")
    new_target = tmp_path / "replica.db"
    cython_replication.SQLiteReplication(db_path=db_path, backup_dir=tmp_path / "cython_backups").replicate_database(str(new_target))

    with fallback_sync.sqlite3.connect(new_target) as conn:
        rows = conn.execute("SELECT COUNT(*) FROM items").fetchone()[0]
    assert rows == 4
