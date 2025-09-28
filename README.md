# SQLitePlus Enhanced

**SQLitePlus Enhanced** es un backend modular en Python con FastAPI que combina:
- 🔐 Autenticación JWT
- 🔄 Operaciones asincrónicas sobre múltiples bases de datos SQLite
- 🧠 Esquemas validados con Pydantic
- 📦 CLI sincrónico con Click
- 🔄 Soporte opcional para replicación, exportación y backups

---

## 🚀 Características principales

- Gestión de múltiples bases SQLite de forma asincrónica (`aiosqlite`)
- API REST completa para creación, inserción, consulta y eliminación de tablas
- JWT con FastAPI + OAuth2 (`/token`)
- CLI para ejecutar acciones sin servidor (`sqliteplus init-db`, etc.)
- Capa de caché opcional con Redis (soporte en utils)
- Cifrado compatible con SQLCipher (modo sincrónico en utils)

---

## 📦 Instalación

> **Requisito:** Necesitas Python 3.10 o superior antes de continuar con la instalación.

```bash
pip install -e .
```
O si quieres publicar:

```bash
pip install sqliteplus-enhanced
```

# 🔐 Configuración obligatoria

Antes de iniciar la aplicación (o ejecutar utilidades como `tests/test3.py`) debes
definir dos variables de entorno críticas:

- `SECRET_KEY`: se utiliza para firmar los tokens JWT.
- `SQLITE_DB_KEY`: se emplea para abrir bases de datos protegidas con SQLCipher.

La aplicación y los scripts rechazarán la ejecución si no las proporcionas.

Genera valores aleatorios en tu entorno con:

```bash
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
export SQLITE_DB_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
```

En Windows (PowerShell):

```powershell
$Env:SECRET_KEY = python -c "import secrets; print(secrets.token_urlsafe(32))"
$Env:SQLITE_DB_KEY = python -c "import secrets; print(secrets.token_hex(32))"
```

# 📡 Ejecutar el servidor

```bash
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
export SQLITE_DB_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
uvicorn sqliteplus.main:app --reload
```

Accede a:

Swagger UI: http://localhost:8000/docs

Redoc: http://localhost:8000/redoc

## 🧪 Ejecutar tests

```bash
pytest -v
```

## 🛠 Uso del CLI

Antes de operar con bases cifradas puedes definir la clave vía variable de entorno
`SQLITE_DB_KEY` o proporcionarla explícitamente con `--cipher-key`.

````bash
export SQLITE_DB_KEY="$(python -c "import secrets; print(secrets.token_hex(32))")"
sqliteplus init-db
sqliteplus execute "INSERT INTO logs (action) VALUES ('via CLI')"
sqliteplus --cipher-key "$SQLITE_DB_KEY" backup
sqliteplus export-csv logs logs.csv
````

## 🧰 Estructura del proyecto

```bash
sqliteplus/
├── main.py                # Punto de entrada FastAPI
├── api/                   # Endpoints REST
├── auth/                  # JWT y seguridad
├── core/                  # DB async + schemas
├── utils/                 # Módulos sync/CLI
└── tests/                 # Tests automatizados

```

## 📝 Licencia

MIT License © Adolfo González