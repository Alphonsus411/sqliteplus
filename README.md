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

### ¿Qué pasa con `bcrypt`?

El paquete incluye una implementación pura en Python que se activa automáticamente si el intérprete no puede importar el módulo oficial. Así, las funciones de autenticación siguen operativas aunque no tengas compiladores o binarios nativos disponibles.

Los hashes generados por el *fallback* llevan el prefijo `compatbcrypt$`. Aunque más adelante instales la extensión oficial, SQLitePlus detecta ese prefijo durante la autenticación y delega la verificación en `sqliteplus._compat.bcrypt`, por lo que puedes mezclar contraseñas nuevas con antiguas sin romper el inicio de sesión.

Si quieres usar la extensión oficial siempre que el entorno lo permita, instala el extra opcional `security`:

```bash
pip install "sqliteplus-enhanced[security]"
```

Cuando el intérprete detecta `bcrypt`, automáticamente sustituye el *fallback* por el módulo nativo. Si deseas migrar las contraseñas antiguas al backend oficial basta con recalcular el hash y actualizar el JSON de usuarios. Un script simple podría iterar por cada entrada con `compatbcrypt$`, verificar la contraseña original (por ejemplo solicitándola al usuario) y escribir un nuevo hash con `bcrypt.hashpw(password.encode(), bcrypt.gensalt())`. Mientras tanto, ambas variantes seguirán funcionando de forma transparente.

---

## 🔐 Configuración mínima

Guarda tus claves como variables de entorno para evitar dejarlas en el código.

### Variables obligatorias para la API y la autenticación

| Variable | Para qué sirve |
| --- | --- |
| `SECRET_KEY` | Firmar los tokens JWT expuestos por la API. |
| `SQLITEPLUS_USERS_FILE` | Ubicación del JSON con usuarios y contraseñas hasheadas con `bcrypt`. Es obligatoria **solo** cuando levantas la API o usas la autenticación integrada. |

### Variables opcionales (API y CLI)

| Variable | Para qué sirve |
| --- | --- |
| `SQLITE_DB_KEY` | Clave SQLCipher para abrir bases cifradas desde la API o la CLI. |
| `SQLITEPLUS_FORCE_RESET` | Valores como `1`, `true` o `on` fuerzan el borrado del archivo SQLite antes de recrear la conexión. |

> Los comandos locales de la CLI no dependen de `SQLITEPLUS_USERS_FILE`; puedes ejecutar `sqliteplus` en modo standalone sin definirlo.

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

Cuando detecta pytest, `AsyncDatabaseManager` borra y recrea las bases ubicadas en `databases/` antes de abrirlas en lugar de moverlas a carpetas temporales. La detección es **perezosa**: en cada `get_connection()` vuelve a comprobar `PYTEST_CURRENT_TEST` y la nueva variable `SQLITEPLUS_FORCE_RESET`, por lo que puedes pedir un reinicio incluso si el gestor global ya se creó (por ejemplo, desde la app FastAPI). Si activas `SQLITEPLUS_FORCE_RESET` mientras una conexión sigue abierta en el mismo bucle de eventos, el gestor la cierra, elimina el archivo `.db` y lo vuelve a crear antes de devolverte la conexión limpia. Revisa la [reinicialización automática en pruebas](https://github.com/Alphonsus411/sqliteplus-enhanced/blob/main/docs/uso_avanzado.md#reinicialización-automática-en-pruebas) o el código correspondiente en [`sqliteplus/core/db.py`](https://github.com/Alphonsus411/sqliteplus-enhanced/blob/main/sqliteplus/core/db.py).

---

## 🛠️ Usar la CLI `sqliteplus`

El comando principal admite dos opciones globales:

- `--cipher-key` o la variable `SQLITE_DB_KEY` para abrir bases cifradas.
- `--db-path` para indicar el archivo de base de datos que usarán todos los subcomandos.

> Nota: Los subcomandos locales no consultan `SQLITEPLUS_USERS_FILE`. Este archivo solo es necesario cuando expones la API protegida con JWT.

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
- `sqliteplus export-query ...` ejecuta una consulta de lectura y guarda el resultado en JSON o CSV; consulta la [guía detallada](https://github.com/Alphonsus411/sqliteplus-enhanced/blob/main/docs/cli.md#exportar-resultados-de-una-consulta).
- `sqliteplus export-csv <tabla> <archivo.csv>` guarda la tabla en un CSV con encabezados y, por defecto, protege archivos existentes a menos que añadas `--overwrite`.
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
