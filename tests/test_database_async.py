import pytest

DB_NAME = "test_db_api"
TABLE_NAME = "logs"

@pytest.mark.asyncio
async def test_create_table(client, auth_headers):
    res = await client.post(
        f"/databases/{DB_NAME}/create_table",
        params={"table_name": TABLE_NAME},
        json={"columns": {"id": "INTEGER PRIMARY KEY", "msg": "TEXT"}},
        headers=auth_headers
    )
    assert res.status_code == 200
    assert "creada" in res.json().get("message", "").lower()


@pytest.mark.asyncio
async def test_insert_and_fetch_data(client, auth_headers):
    # Crear tabla (por seguridad)
    await client.post(
        f"/databases/{DB_NAME}/create_table",
        params={"table_name": TABLE_NAME},
        json={"columns": {"id": "INTEGER PRIMARY KEY", "msg": "TEXT"}},
        headers=auth_headers
    )

    # Insertar mensaje (como JSON válido)
    insert_payload = {"msg": "Hola desde test async"}
    res_insert = await client.post(
        f"/databases/{DB_NAME}/insert?table_name={TABLE_NAME}",
        json=insert_payload,
        headers=auth_headers
    )
    assert res_insert.status_code == 200
    assert "row_id" in res_insert.json()

    # Consultar y validar inserción
    res_fetch = await client.get(
        f"/databases/{DB_NAME}/fetch?table_name={TABLE_NAME}",
        headers=auth_headers
    )
    assert res_fetch.status_code == 200
    data = res_fetch.json().get("data", [])
    assert isinstance(data, list)
    assert any("Hola desde test async" in str(row) for row in data)


@pytest.mark.asyncio
async def test_drop_table(client, auth_headers):
    res = await client.delete(
        f"/databases/{DB_NAME}/drop_table?table_name={TABLE_NAME}",
        headers=auth_headers
    )
    assert res.status_code == 200
    assert f"'{TABLE_NAME}'" in res.json().get("message", "")
