[Leer en español](../api.md)

# REST API - SQLitePlus Enhanced

The API offers CRUD operations on multiple SQLite databases protected by JWT.

> Swagger available at: `http://localhost:8000/docs`

---

## Authentication

### `POST /token`

Generates a JWT token valid for one hour. Credentials are validated against the file defined in `SQLITEPLUS_USERS_FILE`.

> Note: the route is announced relatively in the OpenAPI schema, so in deployments with `root_path` or mounts it will appear as `<prefix>/token`.

- **Body (form-urlencoded)**
  - `username`
  - `password`
- **Responses**
  - `200 OK`: `{ "access_token": "<jwt>", "token_type": "bearer" }`
  - `400 Bad Request`: incorrect credentials or invalid form.
  - `500 Internal Server Error`: problems loading the users file.

---

## Table Management

### `POST /databases/{db_name}/create_table`

Creates a table if it does not exist. Column names are validated using `CreateTableSchema` and escaped with double quotes.

**Normalization and Name Validations**

- Leading/trailing spaces are removed from each name before validating the SQLite pattern.
- Comparison to detect duplicates is done with `casefold()`, so `"Name"` and `" name "` are considered the same identifier.
- If after normalizing there are repeated names, the API responds with `400 Bad Request`.

- **Query**: `table_name` (can include spaces or hyphens; the API will escape it automatically)
- **Body**:

```json
{
  "columns": {
    "id": "INTEGER PRIMARY KEY",
    "msg": "TEXT",
    "created_at": "TEXT"
  }
}
```

- **Common Errors**
  - `400`: invalid table name, duplicate columns, or empty types.
  - `500`: unexpected error in the database.

### `DELETE /databases/{db_name}/drop_table`

Deletes the indicated table. Does not fail if the table does not exist.

- **Query**: `table_name` (mandatory)

```bash
curl -X DELETE "http://127.0.0.1:8000/databases/demo/drop_table?table_name=logs" \
     -H "Authorization: Bearer <TOKEN>"
```

---

## CRUD Operations

### `POST /databases/{db_name}/insert`

Inserts a record into the specified table. The payload can arrive already normalized under the `values` key or as a plain object (for compatibility with simple clients); in the latter case, the API internally restructures it to `{"values": { ... }}` before processing.

- **Query**: `table_name` (mandatory)
- **Body (JSON)**: `{ "values": { "column": "value", ... } }` or `{ "column": "value", ... }`

```bash
curl -X POST "http://127.0.0.1:8000/databases/demo/insert?table_name=logs" \
     -H "Authorization: Bearer <TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{
           "values": {
             "msg": "Text from API"
           }
         }'
```

```bash
curl -X POST "http://127.0.0.1:8000/databases/demo/insert?table_name=logs" \
     -H "Authorization: Bearer <TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"msg": "Text"}'
```

- `404 Not Found`: the table indicated in `table_name` does not exist in the requested database.
- `409 Conflict`: violation of constraints (`UNIQUE`, `NOT NULL`, etc.).

### `GET /databases/{db_name}/fetch`

Returns all rows of the table and includes the name of each column in the response to facilitate consumption from generic clients. The `data` key is an alias of `rows` to maintain compatibility with previous integrations.

- **Query**: `table_name` (mandatory)

```bash
curl -X GET "http://127.0.0.1:8000/databases/demo/fetch?table_name=logs" \
     -H "Authorization: Bearer <TOKEN>"
```

> Note: `404` codes can appear in reads as well as insertions or deletions when the indicated table does not exist.

Example response:

```json
{
  "columns": ["id", "msg", "created_at", "payload"],
  "rows": [
    [1, "Text from API", "2025-05-30T10:00:00", "base64:AQID"]
  ],
  "data": [
    [1, "Text from API", "2025-05-30T10:00:00", "base64:AQID"]
  ]
}
```

- Binary values are returned as strings with prefix `base64:`.
- `date`, `time`, or `datetime` objects are serialized in ISO 8601 format.

---

## Tools and Utilities

### `POST /databases/{db_name}/backup`

Generates a complete backup of the database (including WAL/SHM files if they exist) and returns it as a downloadable file.

- **Response**: Binary file (`application/x-sqlite3`) named `backup_YYYYMMDD_HHMMSS.db`.
- **Errors**:
  - `404 Not Found`: If the database does not exist.
  - `500 Internal Server Error`: If backup generation fails.

```bash
curl -X POST "http://127.0.0.1:8000/databases/demo/backup" \
     -H "Authorization: Bearer <TOKEN>" \
     --output my_backup.db
```

### `GET /databases/{db_name}/export/{table_name}`

Exports the complete content of a table to CSV format.

- **Path Parameters**:
  - `db_name`: Database name.
  - `table_name`: Table name to export.
- **Response**: Downloadable CSV file (`text/csv`).
- **Errors**:
  - `404 Not Found`: If the database or table does not exist.
  - `400 Bad Request`: If the table name is invalid.

```bash
curl -X GET "http://127.0.0.1:8000/databases/demo/export/users" \
     -H "Authorization: Bearer <TOKEN>" \
     --output users.csv
```

---

## General Rules

- All endpoints (except `token`) require `Authorization: Bearer <token>`.
- Database names are normalized and must end in `.db` or the suffix is added.
- Asynchronous and synchronous managers force `PRAGMA journal_mode=WAL` to improve concurrency.
- If `SQLITE_DB_KEY` is defined but empty, the API will return `503 Service Unavailable` in all database operations.
