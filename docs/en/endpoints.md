[Leer en español](../endpoints.md)

# REST Endpoints

Quick summary of available resources. All require `Authorization: Bearer <token>` except the authentication route `token` (which will be published respecting the `root_path`).

## Authentication

- `POST /token` – generates a JWT signed with `SECRET_KEY`. Uses the `SQLITEPLUS_USERS_FILE` file and will be shown as `<prefix>/token` when the app is mounted under a prefix.
- The client IP for rate-limit is obtained from `REMOTE_ADDR` by default. Only if `TRUSTED_PROXIES` contains the remote proxy IP/network are `Forwarded`/`X-Forwarded-For` headers evaluated.

## Database and Table Management

- `POST /databases/{db_name}/create_table` – validates columns with Pydantic, escapes identifiers, and requires `table_name` as a query parameter (e.g., `/databases/db_demo/create_table?table_name=clients`).
- `DELETE /databases/{db_name}/drop_table` – deletes the table if it exists and also requires `table_name` as query (e.g., `/databases/db_demo/drop_table?table_name=clients`).

## CRUD Operations

- `POST /databases/{db_name}/insert` – inserts rows using placeholders `?`, requires `table_name` as query, and responds with `404` if the table does not exist.
- `GET /databases/{db_name}/fetch` – returns all rows of the table indicated in `table_name`; responds with `404` if the table does not exist.

Check `docs/en/api.md` to know the request bodies and detailed responses.
