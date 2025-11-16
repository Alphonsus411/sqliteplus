import builtins
import importlib
import sys
from datetime import datetime

import click
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


def test_fetch_json_normalizes_special_types(monkeypatch):
    runner = CliRunner()
    recorded_queries = []

    class DummySQLitePlus:
        def __init__(self, db_path=None, cipher_key=None):
            pass

        def fetch_query_with_columns(self, query):
            recorded_queries.append(query)
            return (
                ["created_at", "payload"],
                [(datetime(2024, 1, 2, 3, 4, 5), b"\x01\x02\x03")],
            )

    monkeypatch.setattr("sqliteplus.cli.SQLitePlus", DummySQLitePlus)

    result = runner.invoke(
        cli,
        ["fetch", "--output", "json", "SELECT", "*", "FROM", "demo"],
    )

    assert result.exit_code == 0, result.output
    assert "2024-01-02T03:04:05" in result.output
    assert "base64:AQID" in result.output
    assert recorded_queries == ["SELECT * FROM demo"]


def test_cli_commands_work_without_rich(monkeypatch):
    import sqliteplus.cli as cli_module
    import sqliteplus.utils.rich_compat as rich_compat_module

    removed_modules = {
        name: module for name, module in list(sys.modules.items()) if name.startswith("rich")
    }
    for name in removed_modules:
        sys.modules.pop(name, None)

    original_import = builtins.__import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name.startswith("rich"):
            raise ModuleNotFoundError(name)
        return original_import(name, globals, locals, fromlist, level)

    builtins.__import__ = fake_import

    try:
        reloaded_compat = importlib.reload(rich_compat_module)
        reloaded_cli = importlib.reload(cli_module)

        assert reloaded_compat.HAVE_RICH is False

        class DummySQLitePlus:
            def __init__(self, db_path=None, cipher_key=None):
                self.db_path = db_path
                self.cipher_key = cipher_key

            def list_tables(self, include_views=False, include_row_counts=True):
                return [
                    {"name": "demo", "type": "table", "row_count": 2},
                    {"name": "vista", "type": "view", "row_count": None},
                ]

            def get_database_statistics(self):
                return {
                    "path": self.db_path or "demo.db",
                    "size_in_bytes": 4096,
                    "last_modified": datetime(2024, 1, 1, 12, 0, 0),
                    "table_count": 2,
                    "view_count": 1,
                    "total_rows": 2,
                }

        monkeypatch.setattr(reloaded_cli, "SQLitePlus", DummySQLitePlus)

        ctx_tables = click.Context(
            reloaded_cli.list_tables,
            obj={"db_path": "demo.db", "cipher_key": None, "console": reloaded_cli.Console()},
        )
        reloaded_cli.list_tables.callback(ctx_tables, False, False, "system", 12)

        ctx_info = click.Context(
            reloaded_cli.database_info,
            obj={"db_path": "demo.db", "cipher_key": None, "console": reloaded_cli.Console()},
        )
        reloaded_cli.database_info.callback(ctx_info)
    finally:
        builtins.__import__ = original_import
        sys.modules.update(removed_modules)
        importlib.reload(rich_compat_module)
        importlib.reload(cli_module)
