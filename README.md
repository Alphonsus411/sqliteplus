# SQLitePlus Enhanced

**SQLitePlus Enhanced** es una caja de herramientas en Python que facilita el trabajo con bases de datos SQLite. Puedes usarla para levantar una API con FastAPI o para gestionar la base desde la línea de comandos sin escribir código adicional.

## ✨ Qué incluye

- 🔄 Manejo seguro de varias bases SQLite desde tareas asíncronas.
- 🔐 Inicio de sesión mediante JSON Web Tokens con contraseñas protegidas con `bcrypt`.
- 🔑 Compatibilidad opcional con SQLCipher tanto en la API como en la consola.
- 💾 Utilidades sencillas para exportar tablas a CSV y crear copias de seguridad automáticas.
- 🧰 Comando `sqliteplus` con subcomandos claros para tareas diarias.

---

## 📦 Instalación rápida

1. Asegúrate de tener **Python 3.10 o superior**.
2. Instala la librería:

```bash
pip install sqliteplus-enhanced
```

¿Vas a colaborar con el código? Instálala en modo editable y añade las dependencias de desarrollo:

```bash
pip install -e .[dev]
```

Si solo quieres experimentar con la librería dentro del repositorio puedes mantener la instalación mínima:

```bash
pip install -e .
```

---

## 🔐 Configuración mínima

Guarda tus claves como variables de entorno para evitar dejarlas en el código.

| Variable | Obligatoria | Para qué sirve |
| --- | --- | --- |
| `SECRET_KEY` | ✅ | Firmar los tokens JWT de la API. |
| `SQLITEPLUS_USERS_FILE` | ✅ | Ubicación del JSON con usuarios y contraseñas encriptadas con `bcrypt`. |
| `SQLITE_DB_KEY` | Opcional | Clave SQLCipher para abrir bases cifradas desde la API o la CLI. |

Ejemplo rápido para generar valores seguros:

```bash
export SECRET_KEY=$(python -c "import secrets; print(secrets.token_urlsafe(32))")
export SQLITE_DB_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
```

Crear un archivo de usuarios con el login `admin`:

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

## 🚀 Levantar la API

```bash
uvicorn sqliteplus.main:app --reload
```

Una vez en marcha tendrás disponible la documentación interactiva en:

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

---

## 🧪 Ejecutar las pruebas

```bash
pytest -v
```

La capa de base de datos detecta automáticamente las ejecuciones de pytest y utiliza archivos temporales para que cada prueba sea independiente.

---

## 🛠️ Usar la CLI `sqliteplus`

El comando principal admite dos opciones globales:

- `--cipher-key` o la variable `SQLITE_DB_KEY` para abrir bases cifradas.
- `--db-path` para indicar el archivo de base de datos que usarán todos los subcomandos.

Comandos disponibles:

- `sqliteplus init-db` crea la base y deja constancia en la tabla `logs`.
- `sqliteplus execute INSERT ...` ejecuta instrucciones de escritura y muestra el último ID insertado cuando aplica.
- `sqliteplus fetch SELECT ...` muestra los resultados fila por fila, avisando si no hay datos.
- `sqliteplus list-tables` presenta en una tabla rica todas las tablas disponibles y sus recuentos de filas.
- `sqliteplus describe-table <tabla>` resume las columnas, índices y relaciones de la tabla indicada.
- `sqliteplus db-info` muestra un resumen del archivo activo (ruta, tamaño, tablas, vistas y filas totales).
- `sqliteplus export-csv <tabla> <archivo.csv>` guarda la tabla en un CSV con encabezados.
- `sqliteplus backup` genera un respaldo fechado en la carpeta `backups/`. Puedes especificar otra ruta con `--db-path`.

Gracias a la integración con [Rich](https://rich.readthedocs.io/en/stable/) todos los mensajes de la CLI se muestran con colores, paneles y tablas que facilitan su lectura y accesibilidad.

Ejemplo combinando opciones:

```bash
sqliteplus --db-path databases/demo.db --cipher-key "$SQLITE_DB_KEY" backup
```

---

## 🗂️ Estructura del proyecto

```text
sqliteplus/
├── main.py                # Punto de entrada FastAPI
├── api/                   # Endpoints REST protegidos
├── auth/                  # Gestión JWT y validaciones
├── core/                  # Servicios asincrónicos y modelos
├── utils/                 # Herramientas sincrónicas, replicación y CLI
└── tests/                 # Pruebas automatizadas
```

---

## 📝 Licencia

MIT License © Adolfo González Hernández
