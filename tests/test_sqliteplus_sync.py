import os

from sqliteplus.utils.sqliteplus_sync import SQLitePlus


def test_sqliteplus_creates_database_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    db_filename = "database.db"

    SQLitePlus(db_path=db_filename)

    assert os.path.isfile(tmp_path / db_filename)
