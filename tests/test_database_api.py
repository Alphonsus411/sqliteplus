import base64
import sqlite3
from pathlib import Path
from urllib.parse import quote

import pytest
from httpx import AsyncClient, ASGITransport

from sqliteplus import __version__
from sqliteplus.core.db import db_manager
from sqliteplus.main import app

DB_NAME = "test_db_api"
TOKEN_PATH = app.url_path_for("login")


def test_app_version_matches_package_version():
    """La versión de la app debe coincidir con la versión del paquete."""

    assert app.version == __version__


async def _get_auth_headers(client: AsyncClient) -> dict:
    """Obtiene encabezados de autenticación JWT para las peticiones."""
    res_token = await client.post(TOKEN_PATH, data={"username": "admin", "password": "admin"})
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
        assert res_insert.status_code == 200, (
            "La inserción de registros falló: "
            f"status={res_insert.status_code}, body={res_insert.text}"
        )

        # 4. Consultar datos
        res_select = await ac.get(
            f"/databases/{DB_NAME}/fetch?table_name=logs",
            headers=headers
        )
        assert res_select.status_code == 200
        response_json = res_select.json()
        assert "columns" in response_json and "rows" in response_json, (
            "Respuesta inesperada al consultar la tabla: "
            f"{response_json}"
        )

        columns = response_json.get("columns", [])
        rows = response_json.get("rows", [])
        assert isinstance(columns, list)
        assert isinstance(rows, list)
        assert "msg" in columns and "level" in columns
        msg_index = columns.index("msg")
        level_index = columns.index("level")
        assert any(
            row[msg_index] == "Hola desde el test" and row[level_index] == "INFO"
            for row in rows
        ), "El mensaje no fue encontrado en los registros"

        # 5. Eliminar la tabla tras el test
        res_drop = await ac.delete(
            f"/databases/{DB_NAME}/drop_table?table_name=logs",
            headers=headers
        )
        assert res_drop.status_code == 200


@pytest.mark.asyncio
async def test_fetch_serializes_blobs_and_exposes_columns():
    transport = ASGITransport(app=app)
    table_name = "binary_logs"
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await _get_auth_headers(ac)

        create_body = {
            "columns": {
                "id": "INTEGER PRIMARY KEY",
                "payload": "BLOB",
                "created_at": "TEXT",
            }
        }

        res_create = await ac.post(
            f"/databases/{DB_NAME}/create_table",
            params={"table_name": table_name},
            json=create_body,
            headers=headers,
        )
        assert res_create.status_code == 200

        binary_payload = b"\x00\x01payload binario"
        await db_manager.execute_query(
            DB_NAME,
            f'INSERT INTO "{table_name}" (payload, created_at) VALUES (?, ?)',
            (sqlite3.Binary(binary_payload), "2024-01-02T03:04:05"),
        )

        res_fetch = await ac.get(
            f"/databases/{DB_NAME}/fetch?table_name={table_name}",
            headers=headers,
        )
        assert res_fetch.status_code == 200

        payload = res_fetch.json()
        columns = payload["columns"]
        rows = payload["rows"]
        assert columns == ["id", "payload", "created_at"]
        assert len(rows) == 1
        row = rows[0]

        blob_value = row[columns.index("payload")]
        assert blob_value.startswith("base64:")
        decoded = base64.b64decode(blob_value.split(":", 1)[1])
        assert decoded == binary_payload

        timestamp_value = row[columns.index("created_at")]
        assert timestamp_value == "2024-01-02T03:04:05"

        res_drop = await ac.delete(
            f"/databases/{DB_NAME}/drop_table?table_name={table_name}",
            headers=headers,
        )
        assert res_drop.status_code == 200


@pytest.mark.asyncio
async def test_create_table_with_default_injection_returns_bad_request():
    """La API debe rechazar expresiones DEFAULT maliciosas."""
    transport = ASGITransport(app=app)
    table_name = "logs_injection"
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await _get_auth_headers(ac)

        malicious_body = {
            "columns": {
                "id": "INTEGER PRIMARY KEY",
                "message": "TEXT DEFAULT 0); DROP TABLE logs;--",
            }
        }

        res_malicious = await ac.post(
            f"/databases/{DB_NAME}/create_table",
            params={"table_name": table_name},
            json=malicious_body,
            headers=headers,
        )

        assert res_malicious.status_code == 400
        detail = res_malicious.json()["detail"].lower()
        assert "default" in detail

        safe_body = {
            "columns": {
                "id": "INTEGER PRIMARY KEY",
                "message": "TEXT NOT NULL",
            }
        }

        res_safe = await ac.post(
            f"/databases/{DB_NAME}/create_table",
            params={"table_name": table_name},
            json=safe_body,
            headers=headers,
        )

        assert res_safe.status_code == 200

        res_drop = await ac.delete(
            f"/databases/{DB_NAME}/drop_table?table_name={table_name}",
            headers=headers,
        )

        assert res_drop.status_code == 200


@pytest.mark.asyncio
async def test_create_table_with_safe_parenthesized_default():
    """Las expresiones DEFAULT seguras entre paréntesis deben aceptarse."""
    transport = ASGITransport(app=app)
    table_name = "logs_defaults"
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await _get_auth_headers(ac)

        body = {
            "columns": {
                "id": "INTEGER PRIMARY KEY",
                "created_at": "TEXT DEFAULT (CURRENT_TIMESTAMP)",
                "created_local": "TEXT DEFAULT datetime('now')",
            }
        }

        res_create = await ac.post(
            f"/databases/{DB_NAME}/create_table",
            params={"table_name": table_name},
            json=body,
            headers=headers,
        )

        assert res_create.status_code == 200, res_create.text

        res_drop = await ac.delete(
            f"/databases/{DB_NAME}/drop_table?table_name={table_name}",
            headers=headers,
        )

        assert res_drop.status_code == 200


@pytest.mark.asyncio
async def test_create_table_with_multiple_primary_keys_returns_bad_request():
    """La API debe rechazar tablas con más de una columna PRIMARY KEY."""
    transport = ASGITransport(app=app)
    table_name = "duplicated_pk"
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await _get_auth_headers(ac)

        res_create = await ac.post(
            f"/databases/{DB_NAME}/create_table",
            params={"table_name": table_name},
            json={
                "columns": {
                    "id": "INTEGER PRIMARY KEY",
                    "other_id": "INTEGER PRIMARY KEY",
                }
            },
            headers=headers,
        )

        assert res_create.status_code == 400
        detail = res_create.json()["detail"].lower()
        assert "clave primaria" in detail
        assert "more than one primary key" in detail


@pytest.mark.asyncio
async def test_create_table_with_duplicate_normalized_columns_returns_bad_request():
    """Dos nombres que se normalizan al mismo identificador deben rechazarse."""
    transport = ASGITransport(app=app)
    table_name = "duplicated_normalized"
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await _get_auth_headers(ac)

        res_create = await ac.post(
            f"/databases/{DB_NAME}/create_table",
            params={"table_name": table_name},
            json={"columns": {"Name": "TEXT", " name ": "TEXT"}},
            headers=headers,
        )

        assert res_create.status_code == 400
        detail = res_create.json()["detail"].lower()
        assert "duplicado" in detail


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
        payload = res_fetch.json()
        columns = payload.get("columns", [])
        rows = payload.get("rows", [])
        assert len(rows) == 3
        msg_index = columns.index("msg")
        level_index = columns.index("level")
        metadata_index = columns.index("metadata")

        assert rows[0][msg_index] == "Primer registro"
        assert rows[1][msg_index] == "Segundo registro" and rows[1][level_index] == "WARN"
        assert rows[2][msg_index] == "Tercer registro" and rows[2][level_index] == "DEBUG"
        assert rows[2][metadata_index] == '{"trace_id": 123}'

        res_drop = await ac.delete(
            f"/databases/{DB_NAME}/drop_table?table_name={table_name}",
            headers=headers,
        )
        assert res_drop.status_code == 200


@pytest.mark.asyncio
async def test_fetch_nonexistent_table_returns_not_found():
    transport = ASGITransport(app=app)
    table_name = "tabla_inexistente"
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await _get_auth_headers(ac)

        res_fetch = await ac.get(
            f"/databases/{DB_NAME}/fetch?table_name={table_name}",
            headers=headers,
        )

        assert res_fetch.status_code == 404
        assert res_fetch.json()["detail"] == f"Tabla '{table_name}' no encontrada"


@pytest.mark.asyncio
async def test_insert_unique_constraint_violation_returns_conflict():
    """Verifica que las violaciones de restricciones UNIQUE devuelvan 409."""
    transport = ASGITransport(app=app)
    table_name = "logs_unique"
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await _get_auth_headers(ac)

        res_create = await ac.post(
            f"/databases/{DB_NAME}/create_table",
            params={"table_name": table_name},
            json={
                "columns": {
                    "id": "INTEGER PRIMARY KEY",
                    "email": "TEXT UNIQUE",
                }
            },
            headers=headers,
        )
        assert res_create.status_code == 200

        payload = {"values": {"email": "duplicado@example.com"}}

        res_insert_first = await ac.post(
            f"/databases/{DB_NAME}/insert?table_name={table_name}",
            json=payload,
            headers=headers,
        )
        assert res_insert_first.status_code == 200

        res_insert_second = await ac.post(
            f"/databases/{DB_NAME}/insert?table_name={table_name}",
            json=payload,
            headers=headers,
        )

        assert res_insert_second.status_code == 409
        assert "Violación de restricción" in res_insert_second.json()["detail"]

        res_drop = await ac.delete(
            f"/databases/{DB_NAME}/drop_table?table_name={table_name}",
            headers=headers,
        )
        assert res_drop.status_code == 200


@pytest.mark.asyncio
async def test_insert_with_invalid_column_returns_bad_request():
    """Las inserciones con columnas inexistentes deben devolver 400 con detalle claro."""
    transport = ASGITransport(app=app)
    table_name = "logs_invalid_column"
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await _get_auth_headers(ac)

        res_create = await ac.post(
            f"/databases/{DB_NAME}/create_table",
            params={"table_name": table_name},
            json={
                "columns": {
                    "id": "INTEGER PRIMARY KEY",
                    "msg": "TEXT NOT NULL",
                }
            },
            headers=headers,
        )
        assert res_create.status_code == 200

        res_insert = await ac.post(
            f"/databases/{DB_NAME}/insert?table_name={table_name}",
            json={"values": {"msg": "Hola", "extra": "valor"}},
            headers=headers,
        )

        assert res_insert.status_code == 400
        detail = res_insert.json()["detail"]
        assert "Columna inválida" in detail
        assert "extra" in detail

        res_drop = await ac.delete(
            f"/databases/{DB_NAME}/drop_table?table_name={table_name}",
            headers=headers,
        )
        assert res_drop.status_code == 200


@pytest.mark.asyncio
async def test_drop_sqlite_master_returns_bad_request():
    """Eliminar tablas protegidas debe devolver un error controlado."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        headers = await _get_auth_headers(ac)

        response = await ac.delete(
            f"/databases/{DB_NAME}/drop_table?table_name=sqlite_master",
            headers=headers,
        )

        assert response.status_code == 400
        detail = response.json()["detail"].lower()
        assert "no se puede eliminar" in detail


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
