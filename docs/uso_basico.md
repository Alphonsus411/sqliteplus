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

Alternativamente puedes generar hashes con el helper integrado, que delega en
`ensure_bcrypt()` y evita tener que conocer si el backend nativo está
disponible. Si no pasas la contraseña como argumento, se solicitará de forma
oculta con `getpass`:

```bash
python -m sqliteplus.auth.users hash admin
# o bien:
python -m sqliteplus.auth.users hash
```

Cuando ejecutes cualquiera de los ejemplos anteriores sin la dependencia
compilada instalada, `ensure_bcrypt()` activará automáticamente el módulo
`sqliteplus._compat.bcrypt`. Si prefieres trabajar siempre con el backend
oficial instala el extra `security` (`pip install "sqliteplus-enhanced[security]"`).

## 2. Ejecuta los entry points instalados

Después de instalar el paquete tienes disponibles tres comandos en tu `PATH` sin necesidad de llamar a los módulos directamente:

- `sqliteplus`: CLI principal. Usa `--db-path` y `--cipher-key` (o la variable `SQLITE_DB_KEY`) para seleccionar la base y abrirla con SQLCipher si procede. Un flujo mínimo podría ser:

  ```bash
  sqliteplus --db-path ./databases/demo.db init-db
  sqliteplus --db-path ./databases/demo.db execute "INSERT INTO logs (action) VALUES ('Hola desde CLI')"
  sqliteplus --db-path ./databases/demo.db fetch "SELECT * FROM logs"
  ```

- `sqliteplus-sync`: demo síncrona que inicializa la base predeterminada y confirma que las importaciones funcionan desde cualquier carpeta. Si la base está cifrada, exporta `SQLITE_DB_KEY` antes de ejecutarlo.

  ```bash
  sqliteplus-sync
  ```

- `sqliteplus-replication`: prepara una base de demostración, genera un respaldo en `backups/` y exporta `logs_export.csv` en el directorio actual.

  ```bash
  sqliteplus-replication
  ls backups
  ```

> Nota rápida: los entry points resuelven las importaciones de forma aislada; ya no hace falta llamar a los archivos del paquete con `python -m ...` para que funcionen los ejemplos.

## 3. Arranca la API

```bash
uvicorn sqliteplus.main:app --reload
```

## 4. Obtén un token JWT

```bash
BASE_URL=${BASE_URL:-http://127.0.0.1:8000}
curl -X POST "${BASE_URL%/}/token" \
     -H "Content-Type: application/x-www-form-urlencoded" \
     -d "username=admin&password=admin"
```

> Si sirves la aplicación detrás de un `root_path` (por ejemplo `/api/sqlite`), define `BASE_URL` con
> dicho prefijo para que las rutas se resuelvan correctamente.

La respuesta incluye `access_token` y `token_type`.

## 5. Crea una tabla en la base `demo`

```bash
curl -X POST "http://127.0.0.1:8000/databases/demo/create_table?table_name=logs" \
     -H "Authorization: Bearer <TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"columns": {"id": "INTEGER PRIMARY KEY", "msg": "TEXT", "created_at": "TEXT"}}'
```

## 6. Inserta datos

```bash
curl -X POST "http://127.0.0.1:8000/databases/demo/insert?table_name=logs" \
     -H "Authorization: Bearer <TOKEN>" \
     -H "Content-Type: application/json" \
     -d '{"values": {"msg": "Hola desde SQLitePlus"}}'
```

## 7. Consulta los registros

```bash
curl -X GET "http://127.0.0.1:8000/databases/demo/fetch?table_name=logs" \
     -H "Authorization: Bearer <TOKEN>"
```

Recibirás todas las filas de la tabla en formato JSON. El listado aparece bajo
las claves `rows` y `data` (esta última es un alias para compatibilidad con
clientes antiguos).
