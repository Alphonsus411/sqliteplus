"""Microbenchmarks de las APIs críticas comparando modo Cython vs fallback Python."""

import os
from pathlib import Path
from time import perf_counter

import pytest

DML_MIN_EXPECTED_IMPROVEMENT = float(os.getenv("SQLITEPLUS_DML_MIN_SPEEDUP", "0.05"))


def _time_execute_and_fetch(sync_module, db_path: Path) -> float:
    if db_path.exists():
        db_path.unlink()
    client = sync_module.SQLitePlus(db_path=db_path)
    client.execute_query(
        """
        CREATE TABLE IF NOT EXISTS logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            action TEXT NOT NULL
        )
        """
    )
    start = perf_counter()
    for idx in range(120):
        client.execute_query(
            "INSERT INTO logs (action) VALUES (?)", (f"event-{idx}",)
        )
    for _ in range(80):
        client.fetch_query("SELECT id, action FROM logs ORDER BY id DESC")
    return perf_counter() - start


def _time_export(replication_module, sync_module, db_path: Path, csv_path: Path) -> float:
    if db_path.exists():
        db_path.unlink()
    if csv_path.exists():
        csv_path.unlink()
    client = sync_module.SQLitePlus(db_path=db_path)
    for idx in range(150):
        client.execute_query(
            "INSERT INTO logs (action) VALUES (?)", (f"export-{idx}",)
        )
    start = perf_counter()
    replication_module.SQLiteReplication(
        db_path=db_path, backup_dir=db_path.parent / "bench_backups"
    ).export_to_csv("logs", str(csv_path), overwrite=True)
    return perf_counter() - start


@pytest.mark.benchmark(min_rounds=2)
def test_execute_and_fetch_regression_guard(speedup_variants, benchmark, tmp_path):
    _, cython_sync, _ = speedup_variants(force_fallback=False)
    _, fallback_sync, _ = speedup_variants(force_fallback=True)

    def run_both():
        fallback_time = _time_execute_and_fetch(
            fallback_sync, tmp_path / "fallback_logs.db"
        )
        cython_time = _time_execute_and_fetch(
            cython_sync, tmp_path / "cython_logs.db"
        )
        return fallback_time, cython_time

    fallback_time, cython_time = benchmark(run_both)
    assert cython_time <= fallback_time * (1 - DML_MIN_EXPECTED_IMPROVEMENT)


@pytest.mark.benchmark(min_rounds=2)
def test_export_to_csv_regression_guard(speedup_variants, benchmark, tmp_path):
    _, cython_sync, cython_replication = speedup_variants(force_fallback=False)
    _, fallback_sync, fallback_replication = speedup_variants(force_fallback=True)

    def run_both():
        fallback_time = _time_export(
            fallback_replication,
            fallback_sync,
            tmp_path / "fallback_export.db",
            tmp_path / "fallback.csv",
        )
        cython_time = _time_export(
            cython_replication,
            cython_sync,
            tmp_path / "cython_export.db",
            tmp_path / "cython.csv",
        )
        return fallback_time, cython_time

    fallback_time, cython_time = benchmark(run_both)
    assert cython_time <= fallback_time * (1 - DML_MIN_EXPECTED_IMPROVEMENT)
