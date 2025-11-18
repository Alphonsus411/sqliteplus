# Se importa click para poder referenciar click.ClickException en las pruebas.
import click
import pytest

from sqliteplus import cli as cli_module


def _mock_missing_visual_dependencies(monkeypatch):
    original_import_module = cli_module.importlib.import_module

    def fake_import_module(name, package=None):
        if name.startswith("flet"):
            raise ModuleNotFoundError(name)
        return original_import_module(name, package)

    monkeypatch.setattr(cli_module.importlib, "import_module", fake_import_module)


def test_viewer_imports_suggest_visual_extra(monkeypatch):
    _mock_missing_visual_dependencies(monkeypatch)

    with pytest.raises(click.ClickException) as excinfo:
        cli_module._import_visual_viewer_dependencies()

    assert 'pip install "sqliteplus-enhanced[visual]"' in str(excinfo.value)


def test_dashboard_imports_suggest_visual_extra(monkeypatch):
    _mock_missing_visual_dependencies(monkeypatch)

    with pytest.raises(click.ClickException) as excinfo:
        cli_module._import_visual_dashboard_dependencies()

    assert 'pip install "sqliteplus-enhanced[visual]"' in str(excinfo.value)
