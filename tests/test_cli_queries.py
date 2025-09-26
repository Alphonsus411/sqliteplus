from click.testing import CliRunner

from sqliteplus.cli import cli


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
