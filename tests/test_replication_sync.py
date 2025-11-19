import sqlite3
from pathlib import Path

import pytest

from sqliteplus.utils import replication_sync
from sqliteplus.utils.constants import DEFAULT_DB_PATH


def _bootstrap_package_db(package_db: Path) -> None:
    package_db.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(package_db) as conn:
        conn.execute(
            "CREATE TABLE datos (id INTEGER PRIMARY KEY AUTOINCREMENT, valor TEXT)"
        )
        conn.executemany(
            "INSERT INTO datos (valor) VALUES (?)",
            [("uno",), ("dos",)],
        )


def test_replication_uses_local_copy_when_package_is_read_only(tmp_path, monkeypatch):
    package_db = tmp_path / "fake_pkg" / "databases" / "database.db"
    _bootstrap_package_db(package_db)

    wal_data = b"contenido wal"
    shm_data = b"contenido shm"
    package_db.with_name(package_db.name + "-wal").write_bytes(wal_data)
    package_db.with_name(package_db.name + "-shm").write_bytes(shm_data)

    workdir = tmp_path / "workspace"
    workdir.mkdir()

    monkeypatch.chdir(workdir)
    monkeypatch.setattr(replication_sync, "PACKAGE_DB_PATH", package_db)

    replicator = replication_sync.SQLiteReplication(db_path=str(package_db))

    fallback_path = Path(replicator.db_path)
    expected_path = (workdir / DEFAULT_DB_PATH).resolve()
    assert fallback_path == expected_path
    assert fallback_path.exists()

    assert fallback_path.with_name(fallback_path.name + "-wal").read_bytes() == wal_data
    assert fallback_path.with_name(fallback_path.name + "-shm").read_bytes() == shm_data

    with sqlite3.connect(fallback_path) as conn:
        valores = conn.execute("SELECT valor FROM datos ORDER BY id").fetchall()

    assert [row[0] for row in valores] == ["uno", "dos"]


def test_replication_fails_when_package_source_is_missing(tmp_path, monkeypatch):
    package_db = tmp_path / "fake_pkg" / "databases" / "database.db"
    package_db.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(replication_sync, "PACKAGE_DB_PATH", package_db)

    with pytest.raises(FileNotFoundError):
        replication_sync.SQLiteReplication(db_path=str(package_db))
