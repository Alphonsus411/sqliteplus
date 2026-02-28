"""Microbenchmarks de las APIs críticas comparando modo Cython vs fallback Python."""

import os
from pathlib import Path
from time import perf_counter

import pytest

DML_MIN_EXPECTED_IMPROVEMENT = float(os.getenv("SQLITEPLUS_DML_MIN_SPEEDUP", "0.05"))


def _cleanup_file(path: Path):
    """Intenta eliminar un archivo con reintentos para Windows."""
    if not path.exists():
        return
    for _ in range(5):
        try:
            path.unlink()
            return
        except PermissionError:
            import time
            time.sleep(0.1)
    # Si falla después de reintentos, intentar al menos truncarlo o ignorar
    try:
        path.unlink(missing_ok=True)
    except PermissionError:
        pass

def _time_execute_and_fetch(sync_module, db_path: Path) -> float:
    _cleanup_file(db_path)
    # Usar un nombre único por ejecución para evitar conflictos de bloqueo
    unique_db_path = db_path.with_name(f"{db_path.stem}_{perf_counter()}{db_path.suffix}")
    
    client = sync_module.SQLitePlus(db_path=unique_db_path)
    try:
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
    finally:
        # Cerrar explícitamente si el cliente tiene método close (SyncManager lo tiene)
        if hasattr(client, "close_connections"):
             client.close_connections()
        elif hasattr(client, "close"):
             client.close()
        
        # Intentar limpieza
        _cleanup_file(unique_db_path)


def _time_export(replication_module, sync_module, db_path: Path, csv_path: Path) -> float:
    unique_db_path = db_path.with_name(f"{db_path.stem}_{perf_counter()}{db_path.suffix}")
    unique_csv_path = csv_path.with_name(f"{csv_path.stem}_{perf_counter()}{csv_path.suffix}")
    
    _cleanup_file(unique_db_path)
    _cleanup_file(unique_csv_path)
    
    client = sync_module.SQLitePlus(db_path=unique_db_path)
    try:
        client.execute_query(
             """
            CREATE TABLE IF NOT EXISTS logs (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL
            )
            """
        )
        for idx in range(150):
            client.execute_query(
                "INSERT INTO logs (action) VALUES (?)", (f"export-{idx}",)
            )
        start = perf_counter()
        # Cerrar cliente antes de exportar para liberar lock si replication usa otra conexión
        if hasattr(client, "close_connections"):
             client.close_connections()
        
        replication_module.SQLiteReplication(
            db_path=unique_db_path, backup_dir=unique_db_path.parent / "bench_backups"
        ).export_to_csv("logs", str(unique_csv_path), overwrite=True)
        return perf_counter() - start
    finally:
        if hasattr(client, "close_connections"):
             client.close_connections()
        _cleanup_file(unique_db_path)
        _cleanup_file(unique_csv_path)


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
    # En CI o entornos donde no hay compilación real (solo fallback), 
    # cython_time y fallback_time serán casi iguales.
    # Ajustamos la tolerancia si detectamos que estamos en modo "pure python" simulado
    # o si la mejora es despreciable.
    
    # Si cython_sync es en realidad el fallback (no hay extensión compilada),
    # entonces no podemos esperar mejora.
    import sys
    is_compiled = not getattr(cython_sync, "__file__", "").endswith(".py")
    
    if is_compiled:
        assert cython_time <= fallback_time * (1 - DML_MIN_EXPECTED_IMPROVEMENT)
    else:
        # Si no está compilado, solo verificamos que no sea terriblemente más lento (regresión > 25%)
        # En entornos CI windows puede haber fluctuaciones altas
        assert cython_time <= fallback_time * 1.25


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
    
    # Lógica de detección de compilación para evitar falsos positivos en entornos sin build
    import sys
    is_compiled = not getattr(cython_sync, "__file__", "").endswith(".py")

    if is_compiled:
        assert cython_time <= fallback_time * (1 - DML_MIN_EXPECTED_IMPROVEMENT)
    else:
        # En modo fallback, las diferencias de tiempo son ruido estadístico.
        # Aumentamos la tolerancia al 25% para evitar falsos positivos en entornos
        # donde cython_time es ligeramente más lento que fallback_time por fluctuaciones.
        assert cython_time <= fallback_time * 1.25
