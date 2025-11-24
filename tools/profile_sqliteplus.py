"""Script de perfilado para los flujos principales de SQLitePlus.

Ejecuta escenarios predefinidos del CLI y la API aplicando ``cProfile`` y
``pstats``. Los reportes resultantes se guardan en ``reports/profile`` con un
resumen ordenado por tiempo acumulado y número de llamadas.
"""
from __future__ import annotations

import argparse
import cProfile
import io
import json
import os
from pathlib import Path
import pstats
import sys
import time
from typing import Callable, Iterable

from click.testing import CliRunner
from fastapi.testclient import TestClient

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from sqliteplus.cli import cli
from sqliteplus._compat import ensure_bcrypt
from sqliteplus.main import app
from sqliteplus.utils.sqliteplus_sync import SQLitePlus

# Directorio raíz del proyecto y carpeta de reportes.
REPORTS_DIR = REPO_ROOT / "reports" / "profile"

IO_HINTS = (
    "sqlite3",
    "selectors.py",
    "socket.py",
    "ssl.py",
    "asyncio/streams.py",
    "urllib",
    "http",
    "pathlib.py",
    "os.py",
    "io.py",
    "tempfile.py",
    "shutil.py",
)


class ScenarioContext:
    """Recursos compartidos durante la ejecución de un escenario."""

    def __init__(self, workdir: Path):
        self.workdir = workdir
        self.workdir.mkdir(parents=True, exist_ok=True)

    def create_db_with_sample_data(self, name: str = "profile_cli.db") -> Path:
        db_path = self.workdir / name
        db = SQLitePlus(db_path=str(db_path))
        db.execute_query(
            "CREATE TABLE IF NOT EXISTS profile_items ("
            "id INTEGER PRIMARY KEY AUTOINCREMENT, "
            "name TEXT, "
            "value REAL)"
        )
        for index in range(20):
            db.execute_query(
                "INSERT INTO profile_items (name, value) VALUES (?, ?)",
                (f"item-{index}", index * 1.1),
            )
        return db_path

    def ensure_user_file(self, username: str = "profiler", password: str = "profiler") -> Path:
        users_file = self.workdir / "users.json"
        if users_file.exists():
            return users_file

        bcrypt = ensure_bcrypt()
        hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
        users_file.write_text(json.dumps({username: hashed}, indent=2), encoding="utf-8")
        return users_file


# ----------------------- Escenarios de perfilado -----------------------

def scenario_cli_list_tables(context: ScenarioContext) -> None:
    """Ejecuta ``sqliteplus list-tables`` sobre una base de ejemplo."""

    db_path = context.create_db_with_sample_data()
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--db-path", str(db_path), "list-tables", "--include-views"],
        catch_exceptions=False,
    )
    if result.exit_code != 0:
        raise RuntimeError(f"Fallo el comando CLI: {result.output}")


def scenario_cli_db_info(context: ScenarioContext) -> None:
    """Ejecuta ``sqliteplus db-info`` para medir operaciones de inspección."""

    db_path = context.create_db_with_sample_data("profile_cli_info.db")
    runner = CliRunner()
    result = runner.invoke(
        cli,
        ["--db-path", str(db_path), "db-info"],
        catch_exceptions=False,
    )
    if result.exit_code != 0:
        raise RuntimeError(f"Fallo el comando CLI: {result.output}")


def scenario_api_crud(context: ScenarioContext) -> None:
    """Realiza un ciclo simple de la API: token, creación, inserción y lectura."""

    os.environ.setdefault("SECRET_KEY", "sqliteplus-profiler-secret")
    users_file = context.ensure_user_file()
    os.environ["SQLITEPLUS_USERS_FILE"] = str(users_file)
    os.environ.setdefault("SQLITEPLUS_FORCE_RESET", "1")

    client = TestClient(app)

    login = client.post(
        "/token",
        data={"username": "profiler", "password": "profiler"},
    )
    if login.status_code >= 400:
        raise RuntimeError(f"Fallo obteniendo token: {login.text}")
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    db_name = "profile_api"
    table_name = "profile_items"

    create_resp = client.post(
        f"/databases/{db_name}/create_table",
        params={"table_name": table_name},
        json={"columns": {"id": "INTEGER PRIMARY KEY", "payload": "TEXT"}},
        headers=headers,
    )
    if create_resp.status_code >= 400:
        raise RuntimeError(f"Fallo creando tabla: {create_resp.text}")

    for index in range(5):
        insert_resp = client.post(
            f"/databases/{db_name}/insert",
            params={"table_name": table_name},
            json={"values": {"payload": f"valor-{index}"}},
            headers=headers,
        )
        if insert_resp.status_code >= 400:
            raise RuntimeError(f"Fallo insertando datos: {insert_resp.text}")

    fetch_resp = client.get(
        f"/databases/{db_name}/fetch",
        params={"table_name": table_name},
        headers=headers,
    )
    if fetch_resp.status_code >= 400:
        raise RuntimeError(f"Fallo consultando datos: {fetch_resp.text}")


SCENARIOS: dict[str, Callable[[ScenarioContext], None]] = {
    "list_tables": scenario_cli_list_tables,
    "db_info": scenario_cli_db_info,
    "api_crud": scenario_api_crud,
}


# --------------------------- Utilidades ---------------------------

def is_io_function(func_descriptor: tuple[str, int, str]) -> bool:
    filename, _, func_name = func_descriptor
    normalized = str(filename)
    return any(hint in normalized for hint in IO_HINTS) or func_name in {"write", "read", "flush"}


def is_pure_python(func_descriptor: tuple[str, int, str]) -> bool:
    filename, _, _ = func_descriptor
    return str(filename).endswith(".py")


def format_stat_entry(func_descriptor, stats_entry) -> str:
    cc, nc, tt, ct, _ = stats_entry
    filename, lineno, func_name = func_descriptor
    filename_str = str(filename)
    try:
        short_name = Path(filename_str).name
    except Exception:
        short_name = filename_str
    return (
        f"{nc:>7} llamadas | {tt:>8.5f}s propios | {ct:>8.5f}s acumulados | "
        f"{short_name}:{lineno} -> {func_name}"
    )


def summarize_stats(profile: cProfile.Profile, *, top_n: int, skip_io: bool = True) -> str:
    ps = pstats.Stats(profile)
    entries = list(ps.stats.items())

    if skip_io:
        entries = [item for item in entries if not is_io_function(item[0])]

    sorted_by_cumulative = sorted(entries, key=lambda item: item[1][3], reverse=True)[:top_n]
    sorted_by_calls = sorted(entries, key=lambda item: item[1][1], reverse=True)[:top_n]

    python_heavy = [
        item for item in sorted_by_cumulative if is_pure_python(item[0])
    ][:top_n]

    output = io.StringIO()
    output.write("Top por tiempo acumulado" + (" (sin E/S)" if skip_io else "") + "\n")
    output.write("-" * 80 + "\n")
    for entry in sorted_by_cumulative:
        output.write(format_stat_entry(*entry) + "\n")

    output.write("\nTop por número de llamadas" + (" (sin E/S)" if skip_io else "") + "\n")
    output.write("-" * 80 + "\n")
    for entry in sorted_by_calls:
        output.write(format_stat_entry(*entry) + "\n")

    output.write("\nFunciones Python puras destacadas" + (" (sin E/S)" if skip_io else "") + "\n")
    output.write("-" * 80 + "\n")
    for entry in python_heavy:
        output.write(format_stat_entry(*entry) + "\n")

    return output.getvalue()


# ----------------------------- CLI -----------------------------

def run_profile(scenario_name: str, *, top_n: int, include_io: bool) -> Path:
    if scenario_name not in SCENARIOS:
        raise SystemExit(f"Escenario desconocido. Usa uno de: {', '.join(SCENARIOS)}")

    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    timestamp = time.strftime("%Y%m%d-%H%M%S")
    report_path = REPORTS_DIR / f"{scenario_name}-{timestamp}.txt"

    context = ScenarioContext(REPORTS_DIR / "artifacts")
    scenario = SCENARIOS[scenario_name]

    profiler = cProfile.Profile()
    profiler.enable()
    scenario(context)
    profiler.disable()

    summary = summarize_stats(profiler, top_n=top_n, skip_io=not include_io)

    header = (
        f"Reporte de perfilado para '{scenario_name}'\n"
        f"Generado: {time.strftime('%Y-%m-%d %H:%M:%S')}\n"
        f"Directorio de trabajo: {context.workdir}\n"
        f"Filtros: {'incluye E/S' if include_io else 'omitiendo funciones de E/S'}\n"
        f"Top N: {top_n}\n\n"
    )

    report_path.write_text(header + summary, encoding="utf-8")
    return report_path


def parse_args(argv: Iterable[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Perfilador de SQLitePlus con cProfile")
    parser.add_argument(
        "--scenario",
        choices=SCENARIOS.keys(),
        default="list_tables",
        help="Escenario a ejecutar",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=30,
        help="Número de filas a mostrar en los tops",
    )
    parser.add_argument(
        "--include-io",
        action="store_true",
        help="No descartar funciones de entrada/salida en el reporte",
    )
    return parser.parse_args(argv)


def main(argv: Iterable[str] | None = None) -> int:
    args = parse_args(argv)
    report_path = run_profile(
        args.scenario,
        top_n=args.top_n,
        include_io=args.include_io,
    )
    print(f"Reporte guardado en {report_path}")
    return 0


if __name__ == "__main__":  # pragma: no cover - utilidad manual
    try:
        raise SystemExit(main())
    except Exception as exc:  # pragma: no cover - retroalimentación directa
        print(f"Error al generar el perfil: {exc}", file=sys.stderr)
        raise
