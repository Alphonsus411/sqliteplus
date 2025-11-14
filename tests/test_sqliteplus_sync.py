import os
from pathlib import Path

import pytest

from sqliteplus.utils import sqliteplus_sync
from sqliteplus.utils.replication_sync import SQLiteReplication
from sqliteplus.utils.sqliteplus_sync import SQLitePlus, SQLitePlusCipherError


def test_sqliteplus_creates_database_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db_filename = "database.db"

    SQLitePlus(db_path=db_filename)

    assert os.path.isfile(tmp_path / db_filename)


def test_sqliteplus_expands_user_home(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    home_db = Path("~") / "custom.sqlite"
    db = SQLitePlus(db_path=str(home_db))

    assert Path(db.db_path) == (tmp_path / "custom.sqlite").resolve()
    assert Path(db.db_path).exists()


class _DummyCursor:
    def __init__(self, executed):
        self._executed = executed

    def execute(self, query, params=None):
        self._executed.append(("cursor", query, params))

    def fetchall(self):
        return []


class _DummyConnection:
    def __init__(self, executed):
        self.executed = executed
        self.closed = False

    def execute(self, query):
        self.executed.append(("conn", query))

    def cursor(self):
        return _DummyCursor(self.executed)

    def commit(self):
        pass

    def backup(self, other):  # pragma: no cover - solo para compatibilidad
        pass

    def close(self):
        self.closed = True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()


def test_sqliteplus_applies_cipher_key(monkeypatch, tmp_path):
    executed = []

    def fake_connect(path, check_same_thread=False):
        assert check_same_thread is False
        return _DummyConnection(executed)

    monkeypatch.setattr(sqliteplus_sync, "sqlite3", sqliteplus_sync.sqlite3)
    monkeypatch.setattr(sqliteplus_sync.sqlite3, "connect", fake_connect)

    db_path = tmp_path / "encrypted.db"
    db = SQLitePlus(db_path=db_path, cipher_key="mi'clave")

    connection = db.get_connection()
    assert ("conn", "PRAGMA key = 'mi''clave';") in executed
    connection.close()


def test_replication_expands_user_paths(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.setenv("USERPROFILE", str(tmp_path))

    source_db = tmp_path / "source.db"
    database = SQLitePlus(db_path=source_db)
    database.log_action("seed")

    replicator = SQLiteReplication(
        db_path=str(Path("~") / "source.db"),
        backup_dir=str(Path("~") / "backups"),
    )

    assert Path(replicator.db_path) == source_db.resolve()

    backup_path = Path(replicator.backup_database())
    assert backup_path.parent == (tmp_path / "backups").resolve()
    assert backup_path.exists()

    target_path = Path("~") / "replicas" / "copy.db"
    replicated_file = Path(replicator.replicate_database(str(target_path)))
    assert replicated_file == (tmp_path / "replicas" / "copy.db").resolve()
    assert replicated_file.exists()


def test_sqliteplus_raises_cipher_error_when_key_fails(monkeypatch, tmp_path):
    class FailingConnection(_DummyConnection):
        def execute(self, query):
            raise sqliteplus_sync.sqlite3.DatabaseError("no such pragma: key")

    def fake_connect(path, check_same_thread=False):
        return FailingConnection([])

    monkeypatch.setattr(sqliteplus_sync.sqlite3, "connect", fake_connect)

    with pytest.raises(SQLitePlusCipherError):
        SQLitePlus(db_path=tmp_path / "encrypted.db", cipher_key="secret")


def test_describe_table_uses_safe_pragma(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db = SQLitePlus(db_path="meta.db")
    db.execute_query(
        "CREATE TABLE registros (id INTEGER PRIMARY KEY, nombre TEXT NOT NULL)"
    )

    details = db.describe_table("registros")

    assert details["row_count"] == 0
    assert [column["name"] for column in details["columns"]] == [
        "id",
        "nombre",
    ]

    with pytest.raises(ValueError):
        db.describe_table("")


def test_describe_table_accepts_whitespace_and_dash_names(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db = SQLitePlus(db_path="meta.db")
    db.execute_query(
        'CREATE TABLE "logs con espacios" ('
        "id INTEGER PRIMARY KEY AUTOINCREMENT, mensaje TEXT"
        ")"
    )
    db.execute_query(
        'CREATE TABLE "logs-con-guion" ('
        "id INTEGER PRIMARY KEY AUTOINCREMENT, mensaje TEXT"
        ")"
    )
    db.execute_query(
        'INSERT INTO "logs con espacios" (mensaje) VALUES (?)',
        ("evento",),
    )

    info_spaces = db.describe_table("logs con espacios")
    assert info_spaces["row_count"] == 1
    assert [column["name"] for column in info_spaces["columns"]] == [
        "id",
        "mensaje",
    ]

    info_dash = db.describe_table("logs-con-guion")
    assert info_dash["row_count"] == 0
    assert [column["name"] for column in info_dash["columns"]] == [
        "id",
        "mensaje",
    ]
