# tests/test_insert_and_fetch_data.py
import pytest
from urllib.parse import quote

DB_NAME = "test_db_api"
TABLE_NAME = "logs"

@pytest.mark.asyncio
async def test_insert_and_fetch_data(client, auth_headers):
    # Crear la tabla
    await client.post(
        f"/databases/{DB_NAME}/create_table",
        params={"table_name": TABLE_NAME},
        json={"columns": {"id": "INTEGER PRIMARY KEY", "msg": "TEXT"}},
        headers=auth_headers
    )

    # Insertar mensaje
    payload = quote("Hola desde test async")
    res_insert = await client.post(
        f"/databases/{DB_NAME}/insert?table_name={TABLE_NAME}&data={payload}",
        headers=auth_headers
    )
    assert res_insert.status_code == 200

    # Consultar y verificar
    res_fetch = await client.get(
        f"/databases/{DB_NAME}/fetch?table_name={TABLE_NAME}",
        headers=auth_headers
    )
    assert res_fetch.status_code == 200
    data = res_fetch.json().get("data", [])
    assert any("Hola desde test async" in str(row) for row in data)

