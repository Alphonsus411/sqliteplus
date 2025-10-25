# Endpoints REST

Resumen rápido de los recursos disponibles. Todos requieren `Authorization: Bearer <token>` salvo `/token`.

## Autenticación

- `POST /token` – genera un JWT firmado con `SECRET_KEY`. Usa el fichero `SQLITEPLUS_USERS_FILE`.

## Gestión de bases y tablas

- `POST /databases/{db_name}/create_table` – valida columnas con Pydantic y escapa identificadores.
- `DELETE /databases/{db_name}/drop_table` – elimina la tabla si existe.

## Operaciones CRUD

- `POST /databases/{db_name}/insert` – inserta filas usando placeholders `?` para evitar SQL injection.
- `GET /databases/{db_name}/fetch` – devuelve todas las filas de la tabla.

Consulta `docs/api.md` para conocer los cuerpos de petición y respuestas detalladas.
