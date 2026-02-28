# Casos de uso avanzados

## Reinicialización automática en pruebas

`AsyncDatabaseManager` detecta la variable `PYTEST_CURRENT_TEST` y elimina automáticamente la
base temporal antes de cada suite, evitando datos residuales entre ejecuciones. A partir de esta
versión la comprobación es perezosa: el gestor vuelve a leer `PYTEST_CURRENT_TEST`, `SQLITEPLUS_ENV`
y `SQLITEPLUS_FORCE_RESET` cada vez que necesita crear una conexión.

`SQLITEPLUS_FORCE_RESET` solo se honra en entorno seguro (`SQLITEPLUS_ENV=test` o `PYTEST_CURRENT_TEST`
presente). Si se intenta activar fuera de ese contexto, el gestor **no borra archivos** y deja un
warning explícito en logs para evitar pérdidas de datos en producción.

Si la variable se activa en entorno seguro cuando ya existe una conexión viva en el mismo bucle, el
gestor la cierra, elimina los archivos `*.db`, `*.db-wal` y `*.db-shm` y vuelve a levantar una base
limpia.

Para forzar una limpieza manual existe el parámetro `reset_on_init=True`, pensado únicamente para
pruebas y migraciones controladas. Evita usarlo en flujos de producción.

## Conexiones por bucle de eventos

Cuando se reutiliza el mismo nombre de base en distintos bucles de eventos (por ejemplo, al usar
`httpx.AsyncClient` en paralelo), el gestor cierra y recrea la conexión para ese bucle, evitando
errores de "conexión ligada a otro loop".

## Aplicar SQLCipher solo si existe clave
Si `SQLITE_DB_KEY` no está definida, la API trabaja sin cifrado. Si se define como una cadena vacía,
se devuelve un error 503 por seguridad. Al definir la variable con un valor no vacío se ejecuta
`PRAGMA key` y se propagan los posibles errores de SQLCipher en los logs.

## Replicación y exportaciones automatizadas

El módulo `sqliteplus.utils.replication_sync.SQLiteReplication` permite:

- `backup_database()` – genera copias fechadas y duplica archivos WAL/SHM si existen.
- `replicate_database(<ruta>)` – clona la base en otra ruta aplicando la misma clave SQLCipher.
- `export_to_csv(<tabla>, <archivo>)` – exporta columnas y filas preservando el nombre de campos.

A partir de esta versión, al instanciar `SQLiteReplication()` sin argumentos se crea una copia
local en `./sqliteplus/databases/database.db`, exactamente igual que hace la CLI. Esto evita que
los procesos automatizados modifiquen el paquete instalado y garantiza que cualquier replicación o
exportación parta de un archivo sobre el que se puede escribir en el directorio de trabajo. Cuando
el origen solicitado está dentro del paquete o se detecta que no es escribible, el módulo realiza
una copia byte a byte en el directorio local (incluyendo los pares `-wal`/`-shm`). Si la base de
datos original no existe se aborta la operación con un mensaje claro en lugar de crear un archivo
vacío.

## Actualización caliente de usuarios

`sqliteplus.auth.users.get_user_service()` mantiene una caché basada en la firma del archivo. Al
modificar `SQLITEPLUS_USERS_FILE` se detecta el cambio automáticamente y se recarga la lista de
usuarios sin reiniciar el proceso.

## Perfilado de CLI y API

Para detectar cuellos de botella puedes lanzar un perfilado controlado con `cProfile`
mediante los escenarios preparados en `tools/profile_sqliteplus.py`:

```bash
make profile PROFILE_SCENARIO=list_tables           # CLI: inventario de tablas
make profile PROFILE_SCENARIO=db_info               # CLI: resumen de base
make profile PROFILE_SCENARIO=api_crud PROFILE_FLAGS="--include-io"
```

- Los reportes se guardan en `reports/profile/<escenario>-<timestamp>.txt`.
- Por defecto se omiten funciones de E/S habituales (`sqlite3`, `socket`, `pathlib`, etc.)
  para resaltar el coste puramente Python; añade `--include-io` en `PROFILE_FLAGS` si
  necesitas ver la imagen completa.
- El bloque **Top por tiempo acumulado** muestra las funciones que más tiempo absorben
  incluyendo llamadas internas; **Top por número de llamadas** ayuda a detectar rutas
  que se ejecutan en exceso, aunque sean ligeras.
- En la sección **Funciones Python puras destacadas** aparecen solo funciones definidas
  en módulos `.py`, ideales para valorar migraciones a Cython o refactors: céntrate en
  las que combinan alto tiempo acumulado y muchas llamadas, especialmente si pertenecen
  a `sqliteplus` o a utilidades auxiliares que no dependen de I/O.

## Descubrimiento Cython y gemelos `.pyx`

El pipeline de Cython se alimenta de la lista dinámica `reports/cython_candidates.json`.
`setup.py` recorre `sqliteplus/**/*.pyx` y, salvo que definas `SQLITEPLUS_IGNORE_CYTHON_TARGETS=1`,
filtra los módulos con esa lista. El flujo recomendado es:

1. Genera un reporte de hotspots (por ejemplo `reports/hotspots.json`).
2. Ejecuta `tools/generate_cython_twins.py` para crear los gemelos `.pyx` y rellenar el JSON de candidatos:

   ```bash
   python tools/generate_cython_twins.py reports/hotspots.json --limit 3
   ```

   El script crea los `.pyx` junto a cada `.py` (p. ej. `sqliteplus/core/validators.pyx`) y guarda la lista final en `reports/cython_candidates.json`.
   Usa `--overwrite` si necesitas regenerar archivos existentes.
3. Lanza la instalación o el build usando la lista generada:

   ```bash
   SQLITEPLUS_CYTHON_TARGETS=reports/cython_candidates.json python -m build
   ```

Variables útiles para ajustar el comportamiento:

- `SQLITEPLUS_DISABLE_CYTHON=1` apaga la compilación (modo puro Python).
- `SQLITEPLUS_FORCE_CYTHON=1` ignora las listas y compila todos los `.pyx` detectados.
- `SQLITEPLUS_IGNORE_CYTHON_TARGETS=1` recorre todos los `.pyx` pero sigue respetando `SQLITEPLUS_DISABLE_CYTHON`.
- `SQLITEPLUS_CYTHON_TARGETS=/otra/lista.json` apunta a un JSON alternativo con los módulos permitidos.
- `SQLITEPLUS_CYTHON_ANNOTATE=1` y `SQLITEPLUS_CYTHON_TRACE=1` generan HTML de anotación y macros de trazado en los binarios.

Para añadir un módulo a mano, conserva el `.py` original y añade un gemelo `.pyx` en la misma ruta que importe el `.py` como *fallback*.
Si necesitas exponer tipos para `cimport`, acompáñalo de un `.pxd`. Incluye el nuevo módulo en el JSON de candidatos o ejecuta con
`SQLITEPLUS_FORCE_CYTHON=1` para compilarlo en un build concreto. Los `sdist` incluyen los `.py`, `.pyx` y `.pxd`, y los `wheel`
publican los binarios compilados manteniendo los envoltorios `.py` para preservar la API.
