# tests/test_insert_and_fetch_data.py
import pytest

DB_NAME = "test_db_api"
TABLE_NAME = "logs"

@pytest.mark.asyncio
async def test_insert_and_fetch_data(client, auth_headers):
    # Crear la tabla
    res_create = await client.post(
        f"/databases/{DB_NAME}/create_table",
        params={"table_name": TABLE_NAME},
        json={"columns": {"id": "INTEGER PRIMARY KEY", "msg": "TEXT"}},
        headers=auth_headers
    )
    assert res_create.status_code == 200

    # Insertar mensaje con JSON conforme a InsertDataSchema
    insert_payload = {"values": {"msg": "Hola desde test async"}}
    res_insert = await client.post(
        f"/databases/{DB_NAME}/insert?table_name={TABLE_NAME}",
        json=insert_payload,
        headers=auth_headers
    )
    assert res_insert.status_code == 200
    assert "row_id" in res_insert.json()

    # Consultar y verificar
    res_fetch = await client.get(
        f"/databases/{DB_NAME}/fetch?table_name={TABLE_NAME}",
        headers=auth_headers
    )
    assert res_fetch.status_code == 200
    payload = res_fetch.json()
    assert "rows" in payload and "data" in payload
    assert payload["rows"] == payload["data"]
    data = payload["data"]
    assert any("Hola desde test async" in str(row) for row in data)


@pytest.mark.asyncio
async def test_insert_into_missing_table_returns_404(client, auth_headers):
    missing_table = "tabla_inexistente"
    res_insert = await client.post(
        f"/databases/{DB_NAME}/insert?table_name={missing_table}",
        json={"values": {"msg": "hola"}},
        headers=auth_headers,
    )

    assert res_insert.status_code == 404
    assert res_insert.json()["detail"] == f"Tabla '{missing_table}' no encontrada"
