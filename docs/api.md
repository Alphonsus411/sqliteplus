# API REST - SQLitePlus Enhanced

La API ofrece operaciones CRUD sobre múltiples bases SQLite protegidas por JWT.

> Swagger disponible en: `http://localhost:8000/docs`

---

## Autenticación

### `POST /token`

Genera un token JWT válido por una hora. Las credenciales se validan contra el archivo definido en
`SQLITEPLUS_USERS_FILE`.

> Nota: la ruta se anuncia de forma relativa en el esquema OpenAPI, por lo que en despliegues con
> `root_path` o montajes aparecerá como `<prefijo>/token`.

- **Body (form-urlencoded)**
  - `username`
  - `password`
- **Respuestas**
  - `200 OK`: `{ "access_token": "<jwt>", "token_type": "bearer" }`
  - `400 Bad Request`: credenciales incorrectas o formulario inválido.
  - `500 Internal Server Error`: problemas al cargar el archivo de usuarios.

---

## Gestión de tablas

### `POST /databases/{db_name}/create_table`

Crea una tabla si no existe. Los nombres de columnas se validan mediante `CreateTableSchema` y se
escapan con comillas dobles.

- **Query**: `table_name` (puede incluir espacios o guiones; la API lo escapará automáticamente)
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

- **Errores comunes**
  - `400`: nombre de tabla inválido, columnas duplicadas o tipos vacíos.
  - `500`: error inesperado en la base.

### `DELETE /databases/{db_name}/drop_table`

Elimina la tabla indicada. No falla si la tabla no existe.

---

## Operaciones CRUD

### `POST /databases/{db_name}/insert`

Inserta un registro en la tabla especificada.

- **Query**: `table_name` (obligatorio)

```bash
curl -X POST "http://127.0.0.1:8000/databases/demo/insert?table_name=logs" \
     -H "Authorization: Bearer <TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{
           "values": {
             "msg": "Texto desde la API"
           }
         }'
```

- `409 Conflict`: violación de restricciones (`UNIQUE`, `NOT NULL`, etc.).

### `GET /databases/{db_name}/fetch`

Devuelve todas las filas de la tabla.

- **Query**: `table_name` (obligatorio)

```bash
curl -X GET "http://127.0.0.1:8000/databases/demo/fetch?table_name=logs" \
     -H "Authorization: Bearer <TOKEN>"
```

> Nota: Los códigos `404` solo aparecen en operaciones de lectura o borrado cuando la tabla indicada no existe.

Respuesta de ejemplo:

```json
{
  "data": [
    [1, "Texto desde la API", "2025-05-30T10:00:00"]
  ]
}
```

---

## Reglas generales

- Todos los endpoints (excepto `token`) exigen `Authorization: Bearer <token>`.
- Los nombres de base de datos se normalizan y deben terminar en `.db` o se añade el sufijo.
- El gestor asincrónico fuerza `PRAGMA journal_mode=WAL` para mejorar la concurrencia.
