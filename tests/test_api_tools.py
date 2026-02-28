import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_backup_database_endpoint(client: AsyncClient, auth_headers: dict):
    db_name = "test_tools_backup"
    table_name = "backup_test"
    
    # Setup: Create table and insert data
    create_payload = {
        "columns": {"id": "INTEGER PRIMARY KEY", "data": "TEXT"}
    }
    await client.post(
        f"/databases/{db_name}/create_table?table_name={table_name}",
        json=create_payload,
        headers=auth_headers
    )
    
    insert_payload = {"values": {"data": "test_backup"}}
    await client.post(
        f"/databases/{db_name}/insert?table_name={table_name}",
        json=insert_payload,
        headers=auth_headers
    )

    # Act: Request backup
    response = await client.post(f"/databases/{db_name}/backup", headers=auth_headers)

    # Assert
    assert response.status_code == 200
    assert response.headers["content-type"] == "application/x-sqlite3"
    assert response.content.startswith(b"SQLite format 3")

@pytest.mark.asyncio
async def test_export_table_csv_endpoint(client: AsyncClient, auth_headers: dict):
    db_name = "test_tools_export"
    table_name = "export_test"
    
    # Setup: Create table and insert data
    create_payload = {
        "columns": {"id": "INTEGER PRIMARY KEY", "name": "TEXT", "score": "REAL"}
    }
    await client.post(
        f"/databases/{db_name}/create_table?table_name={table_name}",
        json=create_payload,
        headers=auth_headers
    )
    
    insert_payload = {"values": {"name": "Alice", "score": 95.5}}
    await client.post(
        f"/databases/{db_name}/insert?table_name={table_name}",
        json=insert_payload,
        headers=auth_headers
    )

    # Act: Request CSV export
    response = await client.get(
        f"/databases/{db_name}/export/{table_name}",
        headers=auth_headers
    )

    # Assert
    assert response.status_code == 200
    assert "text/csv" in response.headers["content-type"]
    content = response.text
    assert "id,name,score" in content
    assert "Alice,95.5" in content

@pytest.mark.asyncio
async def test_export_nonexistent_table(client: AsyncClient, auth_headers: dict):
    db_name = "test_tools_export"
    response = await client.get(
        f"/databases/{db_name}/export/non_existent_table",
        headers=auth_headers
    )
    assert response.status_code == 404
