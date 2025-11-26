"""Perfilador focalizado en las validaciones de ``sqliteplus.core.schemas``.

Ejecuta escenarios representativos que estresan la normalización de columnas y
la validación de expresiones por defecto. Genera un reporte textual ordenado por
*tiempo acumulado* y *tiempo propio* para identificar rutas candidatas a ser
portadas a Cython.
"""

from __future__ import annotations

import argparse
import cProfile
import io
import sys
import time
from pathlib import Path
from typing import Callable, Iterable

import pstats

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqliteplus.core.schemas import (  # noqa: E402 - import después del sys.path
    CreateTableSchema,
    InsertDataSchema,
    is_valid_sqlite_identifier,
)

SCHEMAS_PATH = (REPO_ROOT / "sqliteplus" / "core" / "schemas.py").resolve()
REPORTS_DIR = REPO_ROOT / "reports" / "profile"
DEFAULT_REPORT = REPORTS_DIR / "schemas_hotpaths.txt"


# ----------------------- Escenarios de trabajo -----------------------

def scenario_normalize_columns(iterations: int) -> None:
    """Ejecuta normalizaciones repetidas con combinaciones comunes de columnas."""

    base_columns = {
        "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
        "email": "TEXT UNIQUE NOT NULL",
        "created_at": "TEXT DEFAULT DATETIME('now')",
        "payload": "BLOB",
    }

    numeric_templates = [
        "NUMERIC DEFAULT -3.14",
        "NUMERIC DEFAULT 42",
        "NUMERIC DEFAULT ROUND(ABS(-15.5))",
        "REAL DEFAULT (3.14159)",
    ]

    for index in range(iterations):
        dynamic_columns = dict(base_columns)
        dynamic_columns["balance"] = numeric_templates[index % len(numeric_templates)]
        dynamic_columns["nickname"] = "TEXT DEFAULT 'anon'"
        schema = CreateTableSchema(columns=dynamic_columns)
        schema.normalized_columns()


def scenario_default_expressions(iterations: int) -> None:
    """Valida expresiones DEFAULT que activan el parser de funciones."""

    expressions = [
        "(CURRENT_TIMESTAMP)",
        "LOWER('ABC')",
        "ROUND(ABS(-42.5))",
        "strftime('%Y-%m-%d', 'now')",
        "COALESCE(NULL, 'fallback')",
        "'texto en español'",
    ]

    for index in range(iterations):
        expr = expressions[index % len(expressions)]
        CreateTableSchema._is_safe_default_expr(expr)  # type: ignore[attr-defined]


def scenario_insert_payloads(iterations: int) -> None:
    """Simula inserciones validadas con nombres a normalizar y múltiples campos."""

    payloads = [
        {" user_id ": 1, " comment": "ok", "score": 9.5},
        {"user_id": 2, "comment": "otro", "score": 7},
        {"user_id": 3, "comment": "más texto", "score": 5.25},
    ]

    for index in range(iterations):
        payload = payloads[index % len(payloads)]
        InsertDataSchema(values=payload)


def scenario_identifier_checks(iterations: int) -> None:
    """Valida identificadores variados para medir el costo del regex y filtros."""

    identifiers = [
        "valid_name",
        "ValidName",
        "nombre_con_acentos",
        "columna123",
        "otra_columna",
        "payload_extra",
        "_prefixed",
        "nombre_largo_con_sufijo_2024",
    ]

    for index in range(iterations * 10):
        candidate = identifiers[index % len(identifiers)]
        is_valid_sqlite_identifier(candidate)


SCENARIOS: dict[str, Callable[[int], None]] = {
    "normalize_columns": scenario_normalize_columns,
    "default_expressions": scenario_default_expressions,
    "insert_payloads": scenario_insert_payloads,
    "identifier_checks": scenario_identifier_checks,
}


# ----------------------- Procesamiento de resultados -----------------------

def _format_entry(func_descriptor: tuple[str, int, str], stats_entry) -> str:
    cc, nc, tt, ct, _ = stats_entry
    filename, lineno, func_name = func_descriptor
    rel_path = Path(filename)
    try:
        rel_path = rel_path.resolve().relative_to(REPO_ROOT)
    except Exception:
        rel_path = Path(filename)
    return (
        f"{nc:>7} llamadas | {tt:>8.5f}s propios | {ct:>8.5f}s acumulados | "
        f"{rel_path}:{lineno} -> {func_name}"
    )


def _collect_schema_entries(stats: pstats.Stats, *, top_n: int):
    entries = [
        item
        for item in stats.stats.items()
        if str(Path(item[0][0]).resolve()) == str(SCHEMAS_PATH)
    ]
    ordered = sorted(entries, key=lambda item: item[1][3], reverse=True)
    return ordered[:top_n]


def profile_scenario(name: str, *, iterations: int, top_n: int) -> tuple[str, float]:
    if name not in SCENARIOS:
        raise SystemExit(
            f"Escenario desconocido '{name}'. Usa uno de: {', '.join(SCENARIOS)}"
        )

    profiler = cProfile.Profile()
    scenario = SCENARIOS[name]

    start = time.perf_counter()
    profiler.enable()
    scenario(iterations)
    profiler.disable()
    duration = time.perf_counter() - start

    stats = pstats.Stats(profiler)
    entries = _collect_schema_entries(stats, top_n=top_n)

    buffer = io.StringIO()
    buffer.write(
        f"Escenario '{name}' (iteraciones: {iterations}) - duración: {duration:.4f}s\n"
    )
    buffer.write("-" * 80 + "\n")
    if not entries:
        buffer.write("No se encontraron llamadas a sqliteplus.core.schemas\n")
        return buffer.getvalue(), duration

    for entry in entries:
        buffer.write(_format_entry(*entry) + "\n")
    buffer.write("\n")

    return buffer.getvalue(), duration


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Perfilador de rutas calientes de validación de esquemas"
    )
    parser.add_argument(
        "--scenario",
        action="append",
        choices=["all", *SCENARIOS.keys()],
        help="Escenarios a ejecutar. Por defecto se ejecutan todos.",
    )
    parser.add_argument(
        "--iterations",
        type=int,
        default=200,
        help="Número de repeticiones por escenario",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=20,
        help="Cantidad de funciones a mostrar por escenario",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=DEFAULT_REPORT,
        help="Ruta de salida para el reporte",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    selected = args.scenario or ["all"]
    scenario_names = list(SCENARIOS) if "all" in selected else selected

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    args.report.parent.mkdir(parents=True, exist_ok=True)

    report = io.StringIO()
    report.write(
        "Reporte de rutas calientes centrado en sqliteplus.core.schemas\n"
    )
    report.write(
        f"Generado: {time.strftime('%Y-%m-%d %H:%M:%S')} | Iteraciones: {args.iterations} | Top N: {args.top_n}\n"
    )
    report.write("=" * 80 + "\n\n")

    durations: dict[str, float] = {}
    for name in scenario_names:
        section, duration = profile_scenario(name, iterations=args.iterations, top_n=args.top_n)
        report.write(section)
        durations[name] = duration

    total_time = sum(durations.values())
    report.write("Resumen de tiempos por escenario\n")
    report.write("-" * 80 + "\n")
    for name, duration in durations.items():
        percentage = (duration / total_time * 100) if total_time else 0.0
        report.write(f"{name:<24} {duration:>8.4f}s ({percentage:5.1f}% del total)\n")

    args.report.write_text(report.getvalue(), encoding="utf-8")
    print(f"Reporte guardado en {args.report}")
    return 0


if __name__ == "__main__":  # pragma: no cover - utilidad manual
    raise SystemExit(main())
