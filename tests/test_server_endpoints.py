import pytest

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

    # 2. Insertar datos válidos
    res_insert = await client.post(
        f"/databases/{DB_NAME}/insert?table_name={TABLE_NAME}",
        json={"msg": "Dato para probar flujo completo"},
        headers=auth_headers
    )
    assert res_insert.status_code == 200

    # 3. Consultar datos
    res_fetch = await client.get(
        f"/databases/{DB_NAME}/fetch?table_name={TABLE_NAME}",
        headers=auth_headers
    )
    assert res_fetch.status_code == 200
    data = res_fetch.json().get("data", [])
    assert any("flujo completo" in str(row) for row in data)


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
