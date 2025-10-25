# SQLitePlus Enhanced

**SQLitePlus Enhanced** es un backend modular en Python que combina FastAPI, SQLite asincrónico y utilidades sincrónicas pensadas para despliegues híbridos.

## 🚀 Características destacadas

- 🔄 **Gestor asincrónico multibase** con `aiosqlite`, bloqueo por base y reapertura automática por bucle de eventos.
- 🔐 **Autenticación JWT** respaldada por un fichero externo de usuarios con contraseñas hasheadas mediante `bcrypt`.
- 🔑 **Compatibilidad opcional con SQLCipher** tanto en la API como en la CLI sincrónica.
- 💾 **Herramientas de replicación**: exportación a CSV, copias de seguridad incrementales con propagación de ficheros `-wal/-shm` y replicación hacia otras rutas.
- 🧠 **Esquemas validados con Pydantic** para operaciones CRUD seguras.
- 🧰 **CLI `sqliteplus`** implementada con Click para tareas administrativas sin servidor.

---

## 📦 Instalación

> **Requisitos mínimos**
>
> - Python 3.10 o superior.
> - SQLite con soporte para WAL (activado por defecto).
> - Dependencias opcionales: Redis si deseas usar la capa de caché sincrónica.

Instalación local editable:

```bash
pip install -e .
```

Instalación desde PyPI:

```bash
pip install sqliteplus-enhanced
```

---

## 🔐 Configuración previa

La API y la CLI utilizan variables de entorno para mantener las credenciales fuera del código.

| Variable | Obligatoria | Descripción |
| --- | --- | --- |
| `SECRET_KEY` | ✅ | Clave utilizada para firmar los tokens JWT. |
| `SQLITEPLUS_USERS_FILE` | ✅ | Ruta a un JSON con hashes `bcrypt` de usuarios autorizados. |
| `SQLITE_DB_KEY` | ⚙️ | Clave SQLCipher opcional. Si se define, se intentará cifrar la base. |

### Generar secretos de ejemplo

```bash
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
export SQLITE_DB_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
```

### Crear el archivo de usuarios

1. Instala `bcrypt` (ya incluido en las dependencias del proyecto).
2. Ejecuta el siguiente fragmento para generar el JSON con el usuario `admin`:

```bash
python - <<'PY'
import bcrypt, json, pathlib

password = "admin"
hash_ = bcrypt.hashpw(password.encode(), bcrypt.gensalt()).decode()
path = pathlib.Path("users.json")
path.write_text(json.dumps({"admin": hash_}, indent=2), encoding="utf-8")
print(f"Archivo generado en {path.resolve()}")
PY

export SQLITEPLUS_USERS_FILE="$(pwd)/users.json"
```

---

## 📡 Ejecutar el servidor

```bash
uvicorn sqliteplus.main:app --reload
```

Endpoints relevantes:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 🧪 Pruebas automatizadas

```bash
pytest -v
```

El gestor asincrónico detecta automáticamente ejecuciones de pytest mediante `PYTEST_CURRENT_TEST` y reinicia las bases temporales para garantizar independencia entre tests.

---

## 🛠 Uso del CLI `sqliteplus`

```bash
sqliteplus --help
```

Subcomandos principales:

- `sqliteplus init-db` – inicializa la base local y registra el evento en `logs`.
- `sqliteplus execute "<SQL>"` – ejecuta consultas de escritura; propaga errores como excepciones de Click.
- `sqliteplus fetch "<SQL>"` – devuelve consultas de lectura.
- `sqliteplus export-csv <tabla> <archivo.csv>` – exporta datos con nombres de columna.
- `sqliteplus backup` – genera copias en `backups/` incluyendo ficheros WAL/SHM.

Puedes definir `SQLITE_DB_KEY` o pasar la opción `--cipher-key` para aplicar SQLCipher:

```bash
export SQLITE_DB_KEY="$(python -c "import secrets; print(secrets.token_hex(32))")"
sqliteplus --cipher-key "$SQLITE_DB_KEY" backup
```

---

## 🧰 Estructura del proyecto

```text
sqliteplus/
├── main.py                # Punto de entrada FastAPI
├── api/                   # Endpoints REST protegidos
├── auth/                  # Gestión JWT + servicio de credenciales externas
├── core/                  # Gestor asincrónico y esquemas Pydantic
├── utils/                 # Herramientas sincrónicas, replicación y CLI
└── tests/                 # Suite de pruebas (httpx, pytest-asyncio)
```

---

## 📝 Licencia

MIT License © Adolfo González Hernández
