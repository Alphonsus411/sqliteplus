import os
import random
import sqlite3
import string
from time import perf_counter

import pytest


MIN_EXPECTED_IMPROVEMENT = float(os.getenv("SQLITEPLUS_MIN_SPEEDUP", "0.2"))
DML_MIN_EXPECTED_IMPROVEMENT = float(os.getenv("SQLITEPLUS_DML_MIN_SPEEDUP", "0.05"))


def _generate_columns(count: int) -> dict[str, str]:
    return {f"col_{idx}": "TEXT NOT NULL" for idx in range(count)}


def _generate_table_names(count: int) -> list[str]:
    alphabet = string.ascii_letters
    names = []
    for idx in range(count):
        suffix = "".join(random.choice(alphabet) for _ in range(6))
        names.append(f"tabla_{idx}_{suffix}")
    return names


@pytest.mark.benchmark(min_rounds=2)
def test_normalized_columns_speedups(benchmark, speedup_variants):
    cython_schemas, _, _ = speedup_variants(force_fallback=False)
    if not cython_schemas.HAS_CYTHON_SPEEDUPS:
        pytest.skip("Extensiones Cython no están disponibles")

    fallback_schemas, _, _ = speedup_variants(force_fallback=True)

    columns = _generate_columns(200)
    iterations = 250

    def run_both_paths():
        start = perf_counter()
        for _ in range(iterations):
            fallback_schemas._normalize_columns_impl(columns)
        fallback_time = perf_counter() - start

        start = perf_counter()
        for _ in range(iterations):
            cython_schemas._normalize_columns_impl(columns)
        cython_time = perf_counter() - start

        return fallback_time, cython_time

    fallback_time, cython_time = benchmark(run_both_paths)

    assert cython_time <= fallback_time * (1 - MIN_EXPECTED_IMPROVEMENT)


@pytest.mark.benchmark(min_rounds=2)
def test_table_listing_speedups(benchmark, speedup_variants, tmp_path):
    cython_schemas, cython_sync, _ = speedup_variants(force_fallback=False)
    if not cython_schemas.HAS_CYTHON_SPEEDUPS:
        pytest.skip("Extensiones Cython no están disponibles")

    _, fallback_sync, _ = speedup_variants(force_fallback=True)

    db_path = tmp_path / "benchmark.db"
    random.seed(42)
    table_names = _generate_table_names(50)

    with sqlite3.connect(db_path) as conn:
        for name in table_names:
            conn.execute(
                f"CREATE TABLE {name} (id INTEGER PRIMARY KEY, value TEXT, created_at TEXT)"
            )

    cython_client = cython_sync.SQLitePlus(db_path=db_path)
    fallback_client = fallback_sync.SQLitePlus(db_path=db_path)

    iterations = 60

    def run_both_paths():
        start = perf_counter()
        for _ in range(iterations):
            for name in table_names:
                fallback_client._escape_identifier(name)
            fallback_client.list_tables(include_views=False, include_row_counts=False)
        fallback_time = perf_counter() - start

        start = perf_counter()
        for _ in range(iterations):
            for name in table_names:
                cython_client._escape_identifier(name)
            cython_client.list_tables(include_views=False, include_row_counts=False)
        cython_time = perf_counter() - start

        return fallback_time, cython_time

    fallback_time, cython_time = benchmark(run_both_paths)

    assert cython_time <= fallback_time * (1 - MIN_EXPECTED_IMPROVEMENT)


@pytest.mark.benchmark(min_rounds=2)
def test_execute_query_speedups(benchmark, speedup_variants, tmp_path):
    cython_schemas, cython_sync, _ = speedup_variants(force_fallback=False)
    if not cython_schemas.HAS_CYTHON_SPEEDUPS:
        pytest.skip("Extensiones Cython no están disponibles")

    _, fallback_sync, _ = speedup_variants(force_fallback=True)

    def time_inserts(sync_module, db_file):
        if db_file.exists():
            db_file.unlink()
        client = sync_module.SQLitePlus(db_path=db_file)
        start = perf_counter()
        for idx in range(200):
            client.execute_query("INSERT INTO logs (action) VALUES (?)", (f"event-{idx}",))
        return perf_counter() - start

    def run_both_paths():
        fallback_time = time_inserts(fallback_sync, tmp_path / "execute_fallback.sqlite")
        cython_time = time_inserts(cython_sync, tmp_path / "execute_cython.sqlite")
        return fallback_time, cython_time

    fallback_time, cython_time = benchmark(run_both_paths)

    assert cython_time <= fallback_time * (1 - DML_MIN_EXPECTED_IMPROVEMENT)


@pytest.mark.benchmark(min_rounds=2)
def test_fetch_query_speedups(benchmark, speedup_variants, tmp_path):
    cython_schemas, cython_sync, _ = speedup_variants(force_fallback=False)
    if not cython_schemas.HAS_CYTHON_SPEEDUPS:
        pytest.skip("Extensiones Cython no están disponibles")

    _, fallback_sync, _ = speedup_variants(force_fallback=True)

    def setup_db(sync_module, db_file):
        if db_file.exists():
            db_file.unlink()
        client = sync_module.SQLitePlus(db_path=db_file)
        for idx in range(400):
            client.execute_query("INSERT INTO logs (action) VALUES (?)", (f"fetch-{idx}",))
        return client

    def time_fetches(sync_module, db_file):
        client = setup_db(sync_module, db_file)
        start = perf_counter()
        for _ in range(120):
            client.fetch_query("SELECT action FROM logs ORDER BY id")
        return perf_counter() - start

    def run_both_paths():
        fallback_time = time_fetches(fallback_sync, tmp_path / "fetch_fallback.sqlite")
        cython_time = time_fetches(cython_sync, tmp_path / "fetch_cython.sqlite")
        return fallback_time, cython_time

    fallback_time, cython_time = benchmark(run_both_paths)

    assert cython_time <= fallback_time * (1 - DML_MIN_EXPECTED_IMPROVEMENT)


@pytest.mark.benchmark(min_rounds=2)
def test_export_to_csv_speedups(benchmark, speedup_variants, tmp_path):
    cython_schemas, cython_sync, cython_replication = speedup_variants(force_fallback=False)
    if not cython_schemas.HAS_CYTHON_SPEEDUPS:
        pytest.skip("Extensiones Cython no están disponibles")

    _, fallback_sync, fallback_replication = speedup_variants(force_fallback=True)

    def time_export(replication_module, sync_module, db_name, csv_name):
        db_path = tmp_path / db_name
        if db_path.exists():
            db_path.unlink()
        csv_path = tmp_path / csv_name
        if csv_path.exists():
            csv_path.unlink()

        client = sync_module.SQLitePlus(db_path=db_path)
        for idx in range(180):
            client.execute_query("INSERT INTO logs (action) VALUES (?)", (f"export-{idx}",))

        start = perf_counter()
        replication_module.SQLiteReplication(
            db_path=db_path, backup_dir=tmp_path / f"backups_{db_name}"
        ).export_to_csv("logs", str(csv_path), overwrite=True)
        return perf_counter() - start

    def run_both_paths():
        fallback_time = time_export(
            fallback_replication, fallback_sync, "export_fallback.sqlite", "fallback.csv"
        )
        cython_time = time_export(
            cython_replication, cython_sync, "export_cython.sqlite", "cython.csv"
        )
        return fallback_time, cython_time

    fallback_time, cython_time = benchmark(run_both_paths)

    assert cython_time <= fallback_time * (1 - DML_MIN_EXPECTED_IMPROVEMENT)
