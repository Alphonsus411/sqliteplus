import sqlite3
from pathlib import Path

from click.testing import CliRunner

from sqliteplus.cli import cli
from sqliteplus.utils.constants import DEFAULT_DB_PATH


def _prepare_database(db_path: Path):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "CREATE TABLE valid_table (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT)"
        )
        conn.executemany(
            "INSERT INTO valid_table (name) VALUES (?)",
            [("Alice",), ("Bob",)],
        )


def test_export_csv_cli_success(tmp_path):
    db_path = tmp_path / "test.db"
    output_path = tmp_path / "out.csv"
    _prepare_database(db_path)

    runner = CliRunner()
    result = runner.invoke(
        cli,
        [
            "export-csv",
            "valid_table",
            str(output_path),
            "--db-path",
            str(db_path),
        ],
    )

    assert result.exit_code == 0, result.output
    content = output_path.read_text(encoding="utf-8").splitlines()
    assert content[0] == "id,name"
    assert content[1].endswith(",Alice")
    assert content[2].endswith(",Bob")


def test_export_csv_cli_rejects_invalid_table_name(tmp_path):
    db_path = tmp_path / "test.db"
    output_path = tmp_path / "out.csv"
    _prepare_database(db_path)

    runner = CliRunner()
    malicious_name = "valid_table; DROP TABLE logs;--"
    result = runner.invoke(
        cli,
        [
            "export-csv",
            malicious_name,
            str(output_path),
            "--db-path",
            str(db_path),
        ],
    )

    assert result.exit_code != 0
    assert "Nombre de tabla inválido" in result.output
    assert not output_path.exists()


def test_backup_cli_creates_backup_file():
    runner = CliRunner()
    with runner.isolated_filesystem():
        db_path = Path(DEFAULT_DB_PATH)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        with sqlite3.connect(db_path) as conn:
            conn.execute("CREATE TABLE demo (id INTEGER PRIMARY KEY)")
            conn.execute("INSERT INTO demo DEFAULT VALUES")

        result = runner.invoke(cli, ["backup"])

        assert result.exit_code == 0, result.output
        backups_dir = Path("backups")
        backups = sorted(backups_dir.glob("backup_*.db"))
        assert backups, "No se creó ningún archivo de respaldo"
        assert backups[0].stat().st_size > 0
