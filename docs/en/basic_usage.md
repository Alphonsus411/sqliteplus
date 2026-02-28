[Leer en español](../uso_basico.md)

# Basic Usage

## 1. Configure environment variables

```bash
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
export SQLITE_DB_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
export SQLITEPLUS_USERS_FILE="$(pwd)/users.json"
```

`SECRET_KEY` is used to sign the JWT tokens issued by the API and to validate the received tokens in each request. Without it, the server cannot generate sessions or verify their authenticity. `SQLITEPLUS_USERS_FILE` is only mandatory for the API protected with JWT; the local CLI can work without that file.

Create the `users.json` file with `bcrypt` hashes:

```bash
python - <<'PY'
from sqliteplus._compat import ensure_bcrypt
import json, pathlib

bcrypt = ensure_bcrypt()
password = "admin"
path = pathlib.Path("users.json")
path.write_text(
    json.dumps({"admin": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()})
)
PY
```

Alternatively, you can generate hashes with the integrated helper, which delegates to `ensure_bcrypt()` and avoids having to know if the native backend is available. If you don't pass the password as an argument, it will be requested hidden with `getpass`:

```bash
python -m sqliteplus.auth.users hash admin
# or:
python -m sqliteplus.auth.users hash
```

When you execute any of the above examples without the compiled dependency installed, `ensure_bcrypt()` will automatically activate the `sqliteplus._compat.bcrypt` module. If you prefer to always work with the official backend, install the `security` extra (`pip install "sqliteplus-enhanced[security]"`).

## 2. Execute installed entry points

After installing the package, you have three commands available in your `PATH` without needing to call the modules directly:

- `sqliteplus`: Main CLI. Use `--db-path` and `--cipher-key` (or the `SQLITE_DB_KEY` variable) to select the database and open it with SQLCipher if applicable. A minimal flow could be:

  ```bash
  sqliteplus --db-path ./databases/demo.db init-db
  sqliteplus --db-path ./databases/demo.db execute "INSERT INTO logs (action) VALUES ('Hello from CLI')"
  sqliteplus --db-path ./databases/demo.db fetch "SELECT * FROM logs"
  ```

- `sqliteplus-sync`: Synchronous demo that initializes the default database and confirms that imports work from any folder. If the database is encrypted, export `SQLITE_DB_KEY` before running it.

  ```bash
  sqliteplus-sync
  ```

- `sqliteplus-replication`: Prepares a demo database, generates a backup in `backups/`, and exports `logs_export.csv` in the current directory.

  ```bash
  sqliteplus-replication
  ls backups
  ```

> **Quick note:** The entry points resolve imports in isolation; you no longer need to call the package files with `python -m ...` for the examples to work.

## 3. Start the API

```bash
uvicorn sqliteplus.main:app --reload
```

## 4. Obtain a JWT token

```bash
BASE_URL=${BASE_URL:-http://127.0.0.1:8000}
curl -X POST "${BASE_URL%/}/token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=admin&password=admin"
```

> If you serve the application behind a `root_path` (e.g., `/api/sqlite`), define `BASE_URL` with that prefix so routes resolve correctly.

The response includes `access_token` and `token_type`.

## 5. Create a table in the `demo` database

```bash
curl -X POST "http://127.0.0.1:8000/databases/demo/create_table?table_name=logs" \
     -H "Authorization: Bearer <TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"columns": {"id": "INTEGER PRIMARY KEY", "msg": "TEXT", "created_at": "TEXT"}}'
```

## 6. Insert data

```bash
curl -X POST "http://127.0.0.1:8000/databases/demo/insert?table_name=logs" \
     -H "Authorization: Bearer <TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"values": {"msg": "Hello from SQLitePlus"}}'
```

## 7. Query records

```bash
curl -X GET "http://127.0.0.1:8000/databases/demo/fetch?table_name=logs" \
     -H "Authorization: Bearer <TOKEN>"
```

You will receive all rows of the table in JSON format. The listing appears under the keys `rows` and `data` (the latter is an alias for compatibility with older clients).
