import pytest
from pathlib import Path
from urllib.parse import quote
from httpx import AsyncClient, ASGITransport
from sqliteplus.main import app

DB_NAME = "test_db_api"

async def _get_auth_headers(client: AsyncClient) -> dict:
    """Obtiene encabezados de autenticación JWT para las peticiones."""
    res_token = await client.post("/token", data={"username": "admin", "password": "admin"})
    assert res_token.status_code == 200
    token = res_token.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}

@pytest.mark.asyncio
async def test_create_table_and_insert_data():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        # 1. Obtener token JWT
        headers = await _get_auth_headers(ac)

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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "malicious_name",
    ["../escape_api", "..\\escape_api", "nested/evil"],
)
async def test_malicious_db_name_rejected(malicious_name):
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await _get_auth_headers(ac)
        base_dir = Path("databases").resolve()
        target_path = (base_dir / Path(f"{malicious_name}.db")).resolve()
        if target_path.exists():
            if target_path.is_file() or target_path.is_symlink():
                target_path.unlink()

        encoded_name = quote(malicious_name, safe="")
        response = await ac.post(
            f"/databases/{encoded_name}/create_table",
            params={"table_name": "logs"},
            json={"columns": {"id": "INTEGER"}},
            headers=headers,
        )

        assert response.status_code == 400
        assert not target_path.exists()
