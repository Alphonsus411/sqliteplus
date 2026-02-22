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

**Normalización y validaciones de nombres**

- Se eliminan espacios iniciales/finales de cada nombre antes de validar el patrón de SQLite.
- La comparación para detectar duplicados se hace con `casefold()`, por lo que `"Nombre"` y
  `" nombre "` se consideran el mismo identificador.
- Si después de normalizar hay nombres repetidos, la API responde con `400 Bad Request`.

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

- **Query**: `table_name` (obligatorio)

```bash
curl -X DELETE "http://127.0.0.1:8000/databases/demo/drop_table?table_name=logs" \
     -H "Authorization: Bearer <TOKEN>"
```

---

## Operaciones CRUD

### `POST /databases/{db_name}/insert`

Inserta un registro en la tabla especificada. El payload puede llegar ya normalizado bajo la
clave `values` o como un objeto plano (por compatibilidad con clientes sencillos); en este último
caso, la API lo reestructura internamente a `{"values": { ... }}` antes de procesarlo.

- **Query**: `table_name` (obligatorio)
- **Body (JSON)**: `{ "values": { "columna": "valor", ... } }` o `{ "columna": "valor", ... }`

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

```bash
curl -X POST "http://127.0.0.1:8000/databases/demo/insert?table_name=logs" \
     -H "Authorization: Bearer <TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"msg": "Texto"}'
```

- `404 Not Found`: la tabla indicada en `table_name` no existe en la base solicitada.
- `409 Conflict`: violación de restricciones (`UNIQUE`, `NOT NULL`, etc.).

### `GET /databases/{db_name}/fetch`

107→Devuelve todas las filas de la tabla e incluye el nombre de cada columna en la
108→respuesta para facilitar el consumo desde clientes genéricos. La clave `data`
109→es un alias de `rows` para mantener compatibilidad con integraciones previas.

- **Query**: `table_name` (obligatorio)

```bash
curl -X GET "http://127.0.0.1:8000/databases/demo/fetch?table_name=logs" \
     -H "Authorization: Bearer <TOKEN>"
```

> Nota: Los códigos `404` pueden aparecer tanto en lecturas como en inserciones o borrados cuando la tabla indicada no existe.

Respuesta de ejemplo:

```json
{
  "columns": ["id", "msg", "created_at", "payload"],
  "rows": [
    [1, "Texto desde la API", "2025-05-30T10:00:00", "base64:AQID"]
  ],
  "data": [
    [1, "Texto desde la API", "2025-05-30T10:00:00", "base64:AQID"]
  ]
}
```

- Los valores binarios se devuelven como cadenas con prefijo `base64:`.
- Los objetos `date`, `time` o `datetime` se serializan en formato ISO 8601.

---

## Reglas generales

- Todos los endpoints (excepto `token`) exigen `Authorization: Bearer <token>`.
- Los nombres de base de datos se normalizan y deben terminar en `.db` o se añade el sufijo.
- Los gestores asincrónico y síncrono fuerzan `PRAGMA journal_mode=WAL` para mejorar la concurrencia.
