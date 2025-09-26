import sqlite3
from pathlib import Path

from click.testing import CliRunner

from sqliteplus.cli import cli


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
