"""Generador de reportes JSON con los puntos calientes de SQLitePlus.

Ejecuta los escenarios críticos definidos en ``tools/profile_sqliteplus.py``
utilizando ``cProfile`` y exporta un resumen en ``reports/hotspots.json`` con
los símbolos que más tiempo consumen. El reporte puede ser usado para
priorizar qué rutas portear a Cython.
"""
from __future__ import annotations

import argparse
import cProfile
import json
import sys
import time
from pathlib import Path
from typing import Iterable

import pstats

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.profile_sqliteplus import (  # noqa: E402 - import tardío para sys.path
    IO_HINTS,
    SCENARIOS,
    ScenarioContext,
    is_io_function,
    is_pure_python,
)

REPORT_PATH = REPO_ROOT / "reports" / "hotspots.json"
ARTIFACTS_DIR = REPO_ROOT / "reports" / "profile" / "artifacts"


def normalize_path(filename: str | Path) -> str:
    """Devuelve la ruta relativa al repositorio cuando es posible."""

    try:
        file_path = Path(filename).resolve()
        return str(file_path.relative_to(REPO_ROOT))
    except Exception:
        return str(filename)


def extract_hotspots(stats: pstats.Stats, *, top_n: int, include_io: bool):
    entries = list(stats.stats.items())
    if not include_io:
        entries = [item for item in entries if not is_io_function(item[0])]

    sorted_entries = sorted(entries, key=lambda item: item[1][3], reverse=True)[:top_n]

    hotspots: list[dict[str, object]] = []
    for func_descriptor, data in sorted_entries:
        _, nc, tt, ct, _ = data
        filename, lineno, func_name = func_descriptor
        hotspots.append(
            {
                "function": func_name,
                "file": normalize_path(filename),
                "line": lineno,
                "ncalls": nc,
                "tottime": round(tt, 6),
                "cumtime": round(ct, 6),
                "is_python": is_pure_python(func_descriptor),
                "is_io": is_io_function(func_descriptor),
            }
        )
    return hotspots


def profile_scenario(
    scenario_name: str, *, top_n: int, include_io: bool
) -> dict[str, object]:
    if scenario_name not in SCENARIOS:
        raise SystemExit(
            f"Escenario desconocido '{scenario_name}'. Usa uno de: {', '.join(SCENARIOS)}"
        )

    scenario = SCENARIOS[scenario_name]
    profiler = cProfile.Profile()
    context = ScenarioContext(ARTIFACTS_DIR)

    start = time.perf_counter()
    profiler.enable()
    scenario(context)
    profiler.disable()
    duration = time.perf_counter() - start

    stats = pstats.Stats(profiler)
    hotspots = extract_hotspots(stats, top_n=top_n, include_io=include_io)

    return {
        "scenario": scenario_name,
        "duration_seconds": round(duration, 4),
        "functions_seen": len(stats.stats),
        "hotspots": hotspots,
    }


def merge_hotspots(results: list[dict[str, object]], *, top_n: int):
    aggregated: dict[tuple[str, int, str], dict[str, object]] = {}

    for scenario_result in results:
        scenario_name = scenario_result["scenario"]  # type: ignore[index]
        for entry in scenario_result["hotspots"]:  # type: ignore[index]
            key = (entry["file"], entry["line"], entry["function"])
            target = aggregated.setdefault(
                key,
                {
                    "function": entry["function"],
                    "file": entry["file"],
                    "line": entry["line"],
                    "ncalls": 0,
                    "tottime": 0.0,
                    "cumtime": 0.0,
                    "is_python": entry["is_python"],
                    "is_io": entry["is_io"],
                    "scenarios": [],
                },
            )
            target["ncalls"] += entry["ncalls"]  # type: ignore[index]
            target["tottime"] += entry["tottime"]  # type: ignore[index]
            target["cumtime"] += entry["cumtime"]  # type: ignore[index]
            target["is_python"] = target["is_python"] and entry["is_python"]  # type: ignore[index]
            target["is_io"] = target["is_io"] or entry["is_io"]  # type: ignore[index]
            target_scenarios = target["scenarios"]  # type: ignore[index]
            if scenario_name not in target_scenarios:
                target_scenarios.append(scenario_name)

    ordered = sorted(aggregated.values(), key=lambda item: item["cumtime"], reverse=True)
    return ordered[:top_n]


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Perfilador JSON de hotspots de SQLitePlus")
    parser.add_argument(
        "--scenario",
        action="append",
        choices=["all", *SCENARIOS.keys()],
        help="Escenarios a ejecutar. Por defecto se ejecutan todos.",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=25,
        help="Número máximo de filas por sección del reporte.",
    )
    parser.add_argument(
        "--include-io",
        action="store_true",
        help="Incluir funciones de E/S en el ranking (por defecto se omiten).",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    scenario_names = args.scenario or ["all"]
    selected = list(SCENARIOS) if "all" in scenario_names else scenario_names

    ARTIFACTS_DIR.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)

    scenario_results = [
        profile_scenario(name, top_n=args.top_n, include_io=args.include_io)
        for name in selected
    ]
    overall = merge_hotspots(scenario_results, top_n=args.top_n)

    report = {
        "generated_at": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "include_io": args.include_io,
        "top_n": args.top_n,
        "scenarios": selected,
        "io_hints": IO_HINTS,
        "by_scenario": scenario_results,
        "overall_hotspots": overall,
    }

    REPORT_PATH.write_text(json.dumps(report, indent=2), encoding="utf-8")
    print(f"Reporte JSON guardado en {REPORT_PATH}")
    return 0


if __name__ == "__main__":  # pragma: no cover - utilidad de línea de comandos
    raise SystemExit(main())
