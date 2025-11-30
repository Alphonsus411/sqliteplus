"""Pruebas que comparan los caminos Cython y puro Python en las APIs de mayor uso.

Las pruebas fuerzan `SQLITEPLUS_DISABLE_CYTHON=1` para el modo *fallback* y
reutilizan el fixture `speedup_variants` para recargar los módulos con la
configuración correcta.
"""

from pathlib import Path

import pytest


def _seed_events(sync_module, db_path: Path) -> None:
    client = sync_module.SQLitePlus(db_path=db_path)
    client.execute_query(
        """
        CREATE TABLE IF NOT EXISTS events (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL,
            priority INTEGER DEFAULT 0
        )
        """
    )
    base_rows = [
        ("alpha", 1),
        ("beta", 2),
        ("gamma", 3),
    ]
    for action, priority in base_rows:
        client.execute_query(
            "INSERT INTO events (action, priority) VALUES (?, ?)",
            (action, priority),
        )


def _exercise_execute_and_fetch(sync_module, db_path: Path):
    _seed_events(sync_module, db_path)
    client = sync_module.SQLitePlus(db_path=db_path)

    extra_actions = ["delta", "epsilon", "zeta"]
    inserted_ids = [
        client.execute_query(
            "INSERT INTO events (action, priority) VALUES (?, ?)", (action, idx)
        )
        for idx, action in enumerate(extra_actions, start=4)
    ]

    rows = client.fetch_query(
        "SELECT id, action, priority FROM events ORDER BY id"
    )
    return inserted_ids, rows


def _export_events(replication_module, sync_module, db_path: Path, csv_path: Path):
    _seed_events(sync_module, db_path)
    replication_module.SQLiteReplication(
        db_path=db_path, backup_dir=db_path.parent / "backups"
    ).export_to_csv("events", str(csv_path), overwrite=True)
    return csv_path.read_text(encoding="utf-8")


def test_execute_and_fetch_match_between_modes(speedup_variants, tmp_path):
    _, cython_sync, _ = speedup_variants(force_fallback=False)
    _, fallback_sync, _ = speedup_variants(force_fallback=True)

    cython_ids, cython_rows = _exercise_execute_and_fetch(
        cython_sync, tmp_path / "cython.db"
    )
    fallback_ids, fallback_rows = _exercise_execute_and_fetch(
        fallback_sync, tmp_path / "fallback.db"
    )

    assert cython_ids == fallback_ids
    assert cython_rows == fallback_rows


def test_export_to_csv_produces_identical_output(speedup_variants, tmp_path):
    _, cython_sync, cython_replication = speedup_variants(force_fallback=False)
    _, fallback_sync, fallback_replication = speedup_variants(force_fallback=True)

    cython_db = tmp_path / "cython_export.db"
    fallback_db = tmp_path / "fallback_export.db"
    cython_csv = tmp_path / "cython.csv"
    fallback_csv = tmp_path / "fallback.csv"

    cython_csv_data = _export_events(cython_replication, cython_sync, cython_db, cython_csv)
    fallback_csv_data = _export_events(
        fallback_replication, fallback_sync, fallback_db, fallback_csv
    )

    assert cython_csv_data == fallback_csv_data

    with cython_sync.sqlite3.connect(cython_db) as conn:
        conn.execute("INSERT INTO events (action, priority) VALUES ('theta', 9)")
        conn.commit()
    with fallback_sync.sqlite3.connect(fallback_db) as conn:
        conn.execute("INSERT INTO events (action, priority) VALUES ('theta', 9)")
        conn.commit()

    cython_replication.SQLiteReplication(
        db_path=cython_db, backup_dir=tmp_path / "cython_backups"
    ).export_to_csv("events", str(cython_csv), overwrite=True)
    fallback_replication.SQLiteReplication(
        db_path=fallback_db, backup_dir=tmp_path / "fallback_backups"
    ).export_to_csv("events", str(fallback_csv), overwrite=True)

    assert cython_csv.read_text(encoding="utf-8") == fallback_csv.read_text(encoding="utf-8")
