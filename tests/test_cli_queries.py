from click.testing import CliRunner

from sqliteplus.cli import _format_numeric, cli


def test_execute_command_reports_sql_error():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["execute", "INSRT INTO demo VALUES (1)"])

    assert result.exit_code != 0
    assert "Error al ejecutar la consulta SQL" in result.output


def test_fetch_command_reports_sql_error():
    runner = CliRunner()
    with runner.isolated_filesystem():
        result = runner.invoke(cli, ["fetch", "SELECT * FROM tabla_inexistente"])

    assert result.exit_code != 0
    assert "Error al ejecutar la consulta SQL" in result.output


def test_cli_passes_cipher_key_to_execute(monkeypatch):
    runner = CliRunner()
    captured = {}

    class DummySQLitePlus:
        def __init__(self, db_path=None, cipher_key=None):
            captured.setdefault("cipher_keys", []).append(cipher_key)

        def execute_query(self, query):
            return 99

    monkeypatch.setattr("sqliteplus.cli.SQLitePlus", DummySQLitePlus)

    result = runner.invoke(
        cli,
        [
            "--cipher-key",
            "clave-test",
            "execute",
            "INSERT INTO demo DEFAULT VALUES",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["cipher_keys"] == ["clave-test"]


def test_format_numeric_uses_single_decimal_separator():
    formatted = _format_numeric(1234.56)

    assert formatted == "1\u202f234.56"
    assert formatted.count(".") == 1
