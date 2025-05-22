import pytest
from httpx import AsyncClient, ASGITransport
from sqliteplus.main import app

DB_NAME = "test_db_api"

@pytest.mark.asyncio
async def test_create_table_and_insert_data():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Obtener token JWT
        res_token = await ac.post("/token", data={"username": "admin", "password": "admin"})
        assert res_token.status_code == 200
        token = res_token.json()["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # 2. Crear tabla
        table_params = {"table_name": "logs"}
        table_body = {"columns": {"id": "INTEGER PRIMARY KEY", "msg": "TEXT"}}
        res_create = await ac.post(
            f"/databases/{DB_NAME}/create_table",
            params=table_params,
            json=table_body,
            headers=headers
        )
        assert res_create.status_code == 200

        # 3. Insertar datos
        res_insert = await ac.post(
            f"/databases/{DB_NAME}/insert?table_name=logs",
            json={"msg": "Hola desde el test"},
            headers=headers
        )

        print("🔎 STATUS:", res_insert.status_code)
        print("🔎 RESPONSE:", res_insert.text)

        assert res_insert.status_code == 200

        # 4. Consultar datos
        res_select = await ac.get(
            f"/databases/{DB_NAME}/fetch?table_name=logs",
            headers=headers
        )
        assert res_select.status_code == 200
        response_json = res_select.json()

        # Mostramos el contenido real si falla
        print("Contenido recibido:", response_json)

        data = response_json.get("data", [])
        assert isinstance(data, list), "La respuesta no contiene una lista válida en 'data'"
        assert any("Hola desde el test" in str(row) for row in data), "El mensaje no fue encontrado en los registros"

        # 5. Eliminar la tabla tras el test
        res_drop = await ac.delete(
            f"/databases/{DB_NAME}/drop_table?table_name=logs",
            headers=headers
        )
        assert res_drop.status_code == 200

