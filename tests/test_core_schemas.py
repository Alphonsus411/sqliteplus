import pytest

from sqliteplus.core.schemas import CreateTableSchema


def test_normalized_columns_accepts_multiple_constraints():
    schema = CreateTableSchema(
        columns={"code": "text default 'hola mundo' not null unique"}
    )
    normalized = schema.normalized_columns()
    assert normalized["code"] == "TEXT NOT NULL UNIQUE DEFAULT 'hola mundo'"


def test_normalized_columns_rejects_invalid_autoincrement():
    schema = CreateTableSchema(columns={"code": "text autoincrement"})
    with pytest.raises(ValueError):
        schema.normalized_columns()
