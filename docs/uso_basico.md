# Uso básico

## 1. Configura las variables de entorno

```bash
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
export SQLITE_DB_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
export SQLITEPLUS_USERS_FILE="$(pwd)/users.json"
```

> `SQLITEPLUS_USERS_FILE` solo es obligatorio para la API protegida con JWT. La CLI local puede trabajar sin ese archivo.

Crea el archivo `users.json` con hashes `bcrypt`:

```bash
python - <<'PY'
import bcrypt, json, pathlib
password = "admin"
path = pathlib.Path("users.json")
path.write_text(json.dumps({"admin": bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()}))
PY
```

## 2. Arranca la API

```bash
uvicorn sqliteplus.main:app --reload
```

## 3. Obtén un token JWT

```bash
BASE_URL=${BASE_URL:-http://127.0.0.1:8000}
curl -X POST "${BASE_URL%/}/token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=admin&password=admin"
```

> Si sirves la aplicación detrás de un `root_path` (por ejemplo `/api/sqlite`), define `BASE_URL` con
> dicho prefijo para que las rutas se resuelvan correctamente.

La respuesta incluye `access_token` y `token_type`.

## 4. Crea una tabla en la base `demo`

```bash
curl -X POST "http://127.0.0.1:8000/databases/demo/create_table?table_name=logs" \
     -H "Authorization: Bearer <TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"columns": {"id": "INTEGER PRIMARY KEY", "msg": "TEXT", "created_at": "TEXT"}}'
```

## 5. Inserta datos

```bash
curl -X POST "http://127.0.0.1:8000/databases/demo/insert?table_name=logs" \
     -H "Authorization: Bearer <TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"values": {"msg": "Hola desde SQLitePlus"}}'
```

## 6. Consulta los registros

```bash
curl -X GET "http://127.0.0.1:8000/databases/demo/fetch?table_name=logs" \
     -H "Authorization: Bearer <TOKEN>"
```

Recibirás todas las filas de la tabla en formato JSON. El listado aparece bajo
las claves `rows` y `data` (esta última es un alias para compatibilidad con
clientes antiguos).
