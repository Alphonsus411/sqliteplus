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
        table_body = {
            "columns": {
                "id": "INTEGER PRIMARY KEY",
                "msg": "TEXT NOT NULL",
                "level": "TEXT",
            }
        }
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
            json={"values": {"msg": "Hola desde el test", "level": "INFO"}},
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
        assert any(
            len(row) >= 3 and row[1] == "Hola desde el test" and row[2] == "INFO"
            for row in data
        ), "El mensaje no fue encontrado en los registros"

        # 5. Eliminar la tabla tras el test
        res_drop = await ac.delete(
            f"/databases/{DB_NAME}/drop_table?table_name=logs",
            headers=headers
        )
        assert res_drop.status_code == 200


@pytest.mark.asyncio
async def test_insert_data_with_varied_columns():
    transport = ASGITransport(app=app)
    table_name = "logs_varied"
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await _get_auth_headers(ac)

        table_body = {
            "columns": {
                "id": "INTEGER PRIMARY KEY",
                "msg": "TEXT NOT NULL",
                "level": "TEXT",
                "metadata": "TEXT",
            }
        }

        res_create = await ac.post(
            f"/databases/{DB_NAME}/create_table",
            params={"table_name": table_name},
            json=table_body,
            headers=headers,
        )
        assert res_create.status_code == 200

        payloads = [
            {"values": {"msg": "Primer registro"}},
            {"values": {"msg": "Segundo registro", "level": "WARN"}},
            {
                "values": {
                    "msg": "Tercer registro",
                    "level": "DEBUG",
                    "metadata": "{\"trace_id\": 123}",
                }
            },
        ]

        for payload in payloads:
            res_insert = await ac.post(
                f"/databases/{DB_NAME}/insert?table_name={table_name}",
                json=payload,
                headers=headers,
            )
            assert res_insert.status_code == 200

        res_fetch = await ac.get(
            f"/databases/{DB_NAME}/fetch?table_name={table_name}",
            headers=headers,
        )
        assert res_fetch.status_code == 200
        data = res_fetch.json().get("data", [])

        assert len(data) == 3
        assert data[0][1] == "Primer registro"
        assert data[1][1] == "Segundo registro" and data[1][2] == "WARN"
        assert data[2][1] == "Tercer registro" and data[2][2] == "DEBUG"
        assert data[2][3] == '{"trace_id": 123}'

        res_drop = await ac.delete(
            f"/databases/{DB_NAME}/drop_table?table_name={table_name}",
            headers=headers,
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
