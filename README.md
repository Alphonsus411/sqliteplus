# SQLitePlus Enhanced

**SQLitePlus Enhanced** es una caja de herramientas en Python que facilita el trabajo con bases de datos SQLite. Puedes usarla para levantar una API con FastAPI o para gestionar la base desde la línea de comandos sin escribir código adicional.

## ✨ Qué incluye

- 🔄 Manejo seguro de varias bases SQLite desde tareas asíncronas.
- 🔐 Inicio de sesión mediante JSON Web Tokens con contraseñas hasheadas con `bcrypt`.
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
pip install -e '.[dev]'
```

> **Nota:** Las comillas simples evitan que shells como `zsh` intenten expandir los corchetes, lo que podría provocar errores al instalar los extras.

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
| `SQLITEPLUS_USERS_FILE` | ✅ | Ubicación del JSON con usuarios y contraseñas hasheadas con `bcrypt`. |
| `SQLITE_DB_KEY` | Opcional | Clave SQLCipher para abrir bases cifradas desde la API o la CLI. |
| `SQLITEPLUS_FORCE_RESET` | Opcional | Valores como `1`, `true` o `on` fuerzan el borrado del archivo SQLite antes de recrear la conexión. |

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

Instala primero las dependencias de desarrollo para disponer de todas las herramientas usadas en la suite:

```bash
pip install -e '.[dev]'
pytest -v
```

Cuando detecta pytest, `AsyncDatabaseManager` borra y recrea las bases ubicadas en `databases/` antes de abrirlas en lugar de moverlas a carpetas temporales. La detección es **perezosa**: en cada `get_connection()` vuelve a comprobar `PYTEST_CURRENT_TEST` y la nueva variable `SQLITEPLUS_FORCE_RESET`, por lo que puedes pedir un reinicio incluso si el gestor global ya se creó (por ejemplo, desde la app FastAPI). Revisa la [reinicialización automática en pruebas](./docs/uso_avanzado.md#reinicialización-automática-en-pruebas) o el código correspondiente en [`sqliteplus/core/db.py`](./sqliteplus/core/db.py).

---

## 🛠️ Usar la CLI `sqliteplus`

El comando principal admite dos opciones globales:

- `--cipher-key` o la variable `SQLITE_DB_KEY` para abrir bases cifradas.
- `--db-path` para indicar el archivo de base de datos que usarán todos los subcomandos.

Si no se especifica `--db-path`, la CLI crea (o reutiliza) automáticamente el archivo
`sqliteplus/databases/database.db` dentro del directorio de trabajo actual, de modo
que no se modifica la base distribuida con el paquete.

Comandos disponibles:

- `sqliteplus init-db` crea la base y deja constancia en la tabla `logs`.
- `sqliteplus execute INSERT ...` ejecuta instrucciones de escritura y muestra el último ID insertado cuando aplica.
- `sqliteplus fetch SELECT ...` muestra los resultados fila por fila, avisando si no hay datos.
- `sqliteplus list-tables` presenta en una tabla rica todas las tablas disponibles y sus recuentos de filas.
- `sqliteplus describe-table <tabla>` resume las columnas, índices y relaciones de la tabla indicada.
- `sqliteplus db-info` muestra un resumen del archivo activo (ruta, tamaño, tablas, vistas y filas totales).
- `sqliteplus export-query ...` ejecuta una consulta de lectura y guarda el resultado en JSON o CSV; consulta la [guía detallada](./docs/cli.md#exportar-resultados-de-una-consulta).
- `sqliteplus export-csv <tabla> <archivo.csv>` guarda la tabla en un CSV con encabezados.
- `sqliteplus backup` genera un respaldo fechado en la carpeta `backups/`. Puedes especificar otra ruta con `--db-path`.

Los subcomandos `export-csv` y `backup` muestran los resultados de forma visual con Rich, mientras que las utilidades internas solo devuelven la ruta generada. Así puedes reutilizar la API desde scripts externos sin producir mensajes duplicados: toda la salida visible procede de la CLI.

### Activar el visor visual (extra opcional)

El paquete base evita instalar dependencias gráficas para mantener una huella ligera. Si deseas abrir el visor accesible de los subcomandos `fetch` o `list-tables` (`--viewer`) o aprovechar `sqliteplus visual-dashboard`, instala el extra opcional `visual`:

```bash
pip install "sqliteplus-enhanced[visual]"
```

Este extra añade Flet y FletPlus. Puedes instalarlo de forma combinada con otros extras (`pip install sqliteplus-enhanced[dev,visual]`).

Gracias a la integración con [Rich](https://rich.readthedocs.io/en/stable/) todos los mensajes de la CLI se muestran con colores, paneles y tablas que facilitan su lectura y accesibilidad.

Ejemplo combinando opciones:

```bash
sqliteplus --db-path databases/demo.db --cipher-key "$SQLITE_DB_KEY" backup
```

---

## 🗂️ Estructura del proyecto

```text
.
├── sqliteplus/            # Paquete instalable
│   ├── main.py            # Punto de entrada FastAPI
│   ├── cli.py             # Implementación del comando `sqliteplus`
│   ├── api/               # Endpoints REST protegidos
│   ├── auth/              # Gestión JWT y validaciones
│   ├── core/              # Servicios asincrónicos y modelos
│   └── utils/             # Herramientas sincrónicas, replicación y helpers CLI
├── tests/                 # Suite de pytest (fuera del paquete)
├── docs/                  # Guías y tutoriales en Markdown
├── databases/             # Bases de ejemplo usadas en demos/pruebas manuales
├── site/                  # Salida estática de la documentación
└── requirements*.txt      # Listados de dependencias para instalación rápida
```

El árbol anterior refleja la jerarquía real: el paquete Python vive en `sqliteplus/` y todo el código de producción (por ej.,
`sqliteplus/cli.py` o `sqliteplus/main.py`) reside allí. Los directorios `tests/`, `docs/`, `databases/` y el resto de archivos
de soporte permanecen en la raíz del repositorio, fuera del paquete publicado.

---

## 📝 Licencia

MIT License © Adolfo González Hernández
