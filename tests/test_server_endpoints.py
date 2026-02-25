import pytest
import aiosqlite
from sqlite3 import OperationalError


DB_NAME = "test_db_api"
TABLE_NAME = "logs"

@pytest.mark.asyncio
async def test_full_data_flow(client, auth_headers):
    # 1. Crear tabla
    res_create = await client.post(
        f"/databases/{DB_NAME}/create_table",
        params={"table_name": TABLE_NAME},
        json={"columns": {"id": "INTEGER PRIMARY KEY", "msg": "TEXT"}},
        headers=auth_headers
    )
    assert res_create.status_code == 200

    # 2. Insertar datos válidos en formatos plano y anidado
    payloads = [
        ("Dato para probar flujo completo", {"msg": "Dato para probar flujo completo"}),
        ("Dato anidado en flujo completo", {"values": {"msg": "Dato anidado en flujo completo"}}),
    ]

    for _, payload in payloads:
        res_insert = await client.post(
            f"/databases/{DB_NAME}/insert?table_name={TABLE_NAME}",
            json=payload,
            headers=auth_headers
        )
        assert res_insert.status_code == 200

    # 3. Consultar datos
    res_fetch = await client.get(
        f"/databases/{DB_NAME}/fetch?table_name={TABLE_NAME}",
        headers=auth_headers
    )
    assert res_fetch.status_code == 200
    payload = res_fetch.json()
    assert "rows" in payload and "data" in payload
    assert payload["rows"] == payload["data"]
    data = payload["data"]
    for expected_text, _ in payloads:
        assert any(expected_text in str(row) for row in data)


@pytest.mark.asyncio
async def test_fetch_nonexistent_table(client, auth_headers):
    res = await client.get(
        f"/databases/{DB_NAME}/fetch?table_name=tabla_inexistente",
        headers=auth_headers
    )
    assert res.status_code == 404


@pytest.mark.asyncio
async def test_insert_without_auth(client):
    res = await client.post(
        f"/databases/{DB_NAME}/insert?table_name={TABLE_NAME}",
        json={"msg": "Sin token"}
    )
    assert res.status_code == 401


@pytest.mark.asyncio
async def test_create_table_rejects_malicious_column_type(client, auth_headers):
    db_name = "test_db_injection_type"
    safe_table = "safe_logs"
    malicious_table = "maliciosa"

    for table in (safe_table, malicious_table):
        await client.delete(
            f"/databases/{db_name}/drop_table?table_name={table}",
            headers=auth_headers,
        )

    try:
        res_create_safe = await client.post(
            f"/databases/{db_name}/create_table",
            params={"table_name": safe_table},
            json={"columns": {"id": "INTEGER PRIMARY KEY", "msg": "TEXT"}},
            headers=auth_headers,
        )
        assert res_create_safe.status_code == 200

        res_insert = await client.post(
            f"/databases/{db_name}/insert?table_name={safe_table}",
            json={"msg": "registro seguro"},
            headers=auth_headers,
        )
        assert res_insert.status_code == 200

        malicious_columns = {"msg": "TEXT); DROP TABLE safe_logs;--"}
        res_malicious = await client.post(
            f"/databases/{db_name}/create_table",
            params={"table_name": malicious_table},
            json={"columns": malicious_columns},
            headers=auth_headers,
        )
        assert res_malicious.status_code == 400

        res_fetch = await client.get(
            f"/databases/{db_name}/fetch?table_name={safe_table}",
            headers=auth_headers,
        )
        assert res_fetch.status_code == 200
        payload = res_fetch.json()
        assert payload["rows"] == payload["data"]
        data = payload["data"]
        assert any("registro seguro" in str(row) for row in data)
    finally:
        for table in (safe_table, malicious_table):
            await client.delete(
                f"/databases/{db_name}/drop_table?table_name={table}",
                headers=auth_headers,
            )


@pytest.mark.asyncio
async def test_create_table_rejects_malicious_column_name(client, auth_headers):
    db_name = "test_db_injection_name"
    safe_table = "safe_logs"
    malicious_table = "maliciosa"

    for table in (safe_table, malicious_table):
        await client.delete(
            f"/databases/{db_name}/drop_table?table_name={table}",
            headers=auth_headers,
        )

    try:
        res_create_safe = await client.post(
            f"/databases/{db_name}/create_table",
            params={"table_name": safe_table},
            json={"columns": {"id": "INTEGER PRIMARY KEY", "msg": "TEXT"}},
            headers=auth_headers,
        )
        assert res_create_safe.status_code == 200

        res_insert = await client.post(
            f"/databases/{db_name}/insert?table_name={safe_table}",
            json={"msg": "registro seguro"},
            headers=auth_headers,
        )
        assert res_insert.status_code == 200

        malicious_columns = {"msg); DROP TABLE safe_logs;--": "TEXT"}
        res_malicious = await client.post(
            f"/databases/{db_name}/create_table",
            params={"table_name": malicious_table},
            json={"columns": malicious_columns},
            headers=auth_headers,
        )
        assert res_malicious.status_code == 400

        res_fetch = await client.get(
            f"/databases/{db_name}/fetch?table_name={safe_table}",
            headers=auth_headers,
        )
        assert res_fetch.status_code == 200
        payload = res_fetch.json()
        assert payload["rows"] == payload["data"]
        data = payload["data"]
        assert any("registro seguro" in str(row) for row in data)
    finally:
        for table in (safe_table, malicious_table):
            await client.delete(
                f"/databases/{db_name}/drop_table?table_name={table}",
                headers=auth_headers,
            )


@pytest.mark.asyncio
async def test_create_table_accepts_multiple_constraints(client, auth_headers):
    db_name = "test_db_multi_constraints"
    table = "rich_schema"

    await client.delete(
        f"/databases/{db_name}/drop_table?table_name={table}",
        headers=auth_headers,
    )

    try:
        columns = {
            "id": "integer primary key autoincrement",
            "code": "text unique not null",
            "created_at": "text default '1970-01-01 00:00:00' not null",
            "score": "real not null default 0.0 unique",
        }

        res_create = await client.post(
            f"/databases/{db_name}/create_table",
            params={"table_name": table},
            json={"columns": columns},
            headers=auth_headers,
        )
        assert res_create.status_code == 200

        res_fetch = await client.get(
            f"/databases/{db_name}/fetch?table_name={table}",
            headers=auth_headers,
        )
        assert res_fetch.status_code == 200
        payload = res_fetch.json()
        assert payload["rows"] == payload["data"]
        assert isinstance(payload["data"], list)
    finally:
        await client.delete(
            f"/databases/{db_name}/drop_table?table_name={table}",
            headers=auth_headers,
        )


@pytest.mark.asyncio
async def test_create_table_error_detail_hides_sql_and_paths(client, auth_headers, monkeypatch):
    async def _failing_execute_query(_db_name, _query, _params=None):
        raise OperationalError(
            "syntax error near SELECT * FROM /abs/private/data.db\nTraceback (most recent call last): ..."
        )

    monkeypatch.setattr("sqliteplus.api.endpoints.db_manager.execute_query", _failing_execute_query)

    response = await client.post(
        "/databases/test_db_api/create_table",
        params={"table_name": "logs"},
        json={"columns": {"id": "INTEGER PRIMARY KEY", "msg": "TEXT"}},
        headers=auth_headers,
    )

    assert response.status_code == 400
    detail = response.json()["detail"]
    assert detail == "La operación no pudo completarse por una sintaxis SQL inválida"
    assert "/abs/private" not in detail
    assert "select *" not in detail.lower()
    assert "traceback" not in detail.lower()


@pytest.mark.asyncio
async def test_insert_integrity_error_hides_sql_and_schema_details(client, auth_headers, monkeypatch):
    async def _failing_execute_query(_db_name, _query, _params=None):
        raise aiosqlite.IntegrityError(
            "UNIQUE constraint failed: users.email; index ux_users_email; SQL: INSERT INTO users(email) VALUES('a@x.com')"
        )

    monkeypatch.setattr("sqliteplus.api.endpoints.db_manager.execute_query", _failing_execute_query)

    response = await client.post(
        "/databases/test_db_api/insert",
        params={"table_name": "users"},
        json={"values": {"email": "a@x.com"}},
        headers=auth_headers,
    )

    assert response.status_code == 409
    detail = response.json()["detail"]
    assert detail == "No se pudo insertar por restricción de unicidad"
    assert "users" not in detail.lower()
    assert "index" not in detail.lower()
    assert "insert into" not in detail.lower()
