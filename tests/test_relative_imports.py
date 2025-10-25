import os
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parents[1]
CLI_SCRIPT = PROJECT_ROOT / "sqliteplus" / "cli.py"
SQLITEPLUS_SYNC_SCRIPT = PROJECT_ROOT / "sqliteplus" / "utils" / "sqliteplus_sync.py"
REPLICATION_SCRIPT = PROJECT_ROOT / "sqliteplus" / "utils" / "replication_sync.py"


def _run_script(script: Path, *args: str, cwd: Path) -> subprocess.CompletedProcess[str]:
    command = [sys.executable, str(script), *args]
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        cwd=cwd,
        env=os.environ.copy(),
        check=False,
    )


def test_cli_script_runs_from_outside_project(tmp_path: Path) -> None:
    result = _run_script(CLI_SCRIPT, "--help", cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "SQLitePlus" in result.stdout


def test_sqliteplus_sync_demo_runs_from_outside_project(tmp_path: Path) -> None:
    result = _run_script(SQLITEPLUS_SYNC_SCRIPT, cwd=tmp_path)
    assert result.returncode == 0, result.stderr
    assert "SQLitePlus está listo para usar." in result.stdout


def test_replication_script_creates_artifacts(tmp_path: Path) -> None:
    result = _run_script(REPLICATION_SCRIPT, cwd=tmp_path)
    assert result.returncode == 0, result.stderr

    backups_dir = tmp_path / "backups"
    assert backups_dir.exists() and any(backups_dir.iterdir())
    assert (tmp_path / "logs_export.csv").exists()
