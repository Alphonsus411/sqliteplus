import os
import subprocess
import sys
from pathlib import Path

# `os` is required for environment handling inside helper functions below.
PROJECT_ROOT = Path(__file__).resolve().parents[1]


def _ensure_package_installed() -> None:
    if getattr(_ensure_package_installed, "_installed", False):
        return

    env = os.environ.copy()
    env["SQLITEPLUS_DISABLE_CYTHON"] = "1"

    subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", str(PROJECT_ROOT)],
        capture_output=True,
        text=True,
        check=True,
        env=env,
    )
    _ensure_package_installed._installed = True


def _run_entrypoint(command: str, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    _ensure_package_installed()
    return subprocess.run(
        [command, *args],
        capture_output=True,
        text=True,
        cwd=cwd,
        env=os.environ.copy(),
        check=False,
    )


def test_cli_script_runs_from_outside_project(tmp_path: Path) -> None:
    result = _run_entrypoint("sqliteplus", "--help", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "SQLitePlus" in result.stdout


def test_sqliteplus_sync_demo_runs_from_outside_project(tmp_path: Path) -> None:
    result = _run_entrypoint("sqliteplus-sync", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "SQLitePlus está listo para usar." in result.stdout


def test_replication_script_creates_artifacts(tmp_path: Path) -> None:
    result = _run_entrypoint("sqliteplus-replication", cwd=tmp_path)
    assert result.returncode == 0, result.stderr

    backups_dir = tmp_path / "backups"
    assert backups_dir.exists() and any(backups_dir.iterdir())
    assert (tmp_path / "logs_export.csv").exists()
