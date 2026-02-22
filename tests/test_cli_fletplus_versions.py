import json
from email.message import Message
from urllib.error import URLError

import pytest

from sqliteplus import cli


class _FakeResponse:
    def __init__(self, body: bytes, *, status: int = 200, content_type: str = "application/json"):
        self._body = body
        self._status = status
        self.headers = Message()
        self.headers["Content-Type"] = content_type

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False

    def getcode(self):
        return self._status

    def read(self, limit: int | None = None):
        if limit is None:
            return self._body
        return self._body[:limit]


def test_fetch_latest_fletplus_version_success(monkeypatch):
    payload = json.dumps({"info": {"version": "9.9.9"}}).encode("utf-8")

    monkeypatch.setattr(
        cli.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _FakeResponse(payload),
    )

    assert cli._fetch_latest_fletplus_version() == "9.9.9"


@pytest.mark.parametrize(
    ("url", "response", "error_message"),
    [
        ("http://pypi.org/pypi/fletplus/json", _FakeResponse(b"{}"), "HTTPS"),
        (cli._PYPI_FLETPLUS_URL, _FakeResponse(b"{}", status=503), "Código HTTP"),
        (
            cli._PYPI_FLETPLUS_URL,
            _FakeResponse(b"{}", content_type="text/html"),
            "Content-Type",
        ),
    ],
)
def test_fetch_latest_fletplus_version_validates_transport(monkeypatch, url, response, error_message):
    monkeypatch.setattr(cli.urllib.request, "urlopen", lambda *args, **kwargs: response)

    with pytest.raises(ValueError, match=error_message):
        cli._fetch_latest_fletplus_version(url)


def test_fetch_latest_fletplus_version_rejects_large_payload(monkeypatch):
    monkeypatch.setattr(
        cli.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _FakeResponse(b"{" + b"a" * 100),
    )

    with pytest.raises(ValueError, match="excede"):
        cli._fetch_latest_fletplus_version(max_payload_bytes=10)


def test_resolve_fletplus_versions_handles_offline_mode(monkeypatch, caplog):
    monkeypatch.setattr(cli.importlib.metadata, "version", lambda name: "1.2.3")

    def _raise_url_error(*args, **kwargs):
        raise URLError("sin red")

    monkeypatch.setattr(cli.urllib.request, "urlopen", _raise_url_error)

    with caplog.at_level("DEBUG"):
        result = cli._resolve_fletplus_versions()

    assert result == {
        "installed": "1.2.3",
        "latest": None,
        "error": "No se pudo comprobar la última versión en PyPI.",
    }
    assert "Fallo de red" in caplog.text


def test_resolve_fletplus_versions_handles_invalid_json(monkeypatch, caplog):
    monkeypatch.setattr(cli.importlib.metadata, "version", lambda name: "1.2.3")
    monkeypatch.setattr(
        cli.urllib.request,
        "urlopen",
        lambda *args, **kwargs: _FakeResponse(b"{"),
    )

    with caplog.at_level("DEBUG"):
        result = cli._resolve_fletplus_versions()

    assert result["error"] == "No se pudo comprobar la última versión en PyPI."
    assert "Respuesta inválida" in caplog.text
