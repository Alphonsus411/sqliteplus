# Endpoints REST

Resumen rápido de los recursos disponibles. Todos requieren `Authorization: Bearer <token>` salvo la
ruta de autenticación `token` (que se publicará respetando el `root_path`).

## Autenticación

- `POST /token` – genera un JWT firmado con `SECRET_KEY`. Usa el fichero `SQLITEPLUS_USERS_FILE` y se
  mostrará como `<prefijo>/token` cuando la app se monte bajo un prefijo.

## Gestión de bases y tablas

- `POST /databases/{db_name}/create_table` – valida columnas con Pydantic, escapa identificadores y requiere `table_name` como parámetro de consulta (por ejemplo, `/databases/db_demo/create_table?table_name=clientes`).
- `DELETE /databases/{db_name}/drop_table` – elimina la tabla si existe y también exige `table_name` como query (ejemplo: `/databases/db_demo/drop_table?table_name=clientes`).

## Operaciones CRUD

- `POST /databases/{db_name}/insert` – inserta filas usando placeholders `?`, requiere `table_name` como query y responde con `404` si la tabla no existe.
- `GET /databases/{db_name}/fetch` – devuelve todas las filas de la tabla indicado en `table_name`; responde con `404` si la tabla no existe.

Consulta `docs/api.md` para conocer los cuerpos de petición y respuestas detalladas.
