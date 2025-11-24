# Casos de uso avanzados

## Reinicialización automática en pruebas

`AsyncDatabaseManager` detecta la variable `PYTEST_CURRENT_TEST` y elimina automáticamente la
base temporal antes de cada suite, evitando datos residuales entre ejecuciones. A partir de esta
versión la comprobación es perezosa: el gestor vuelve a leer `PYTEST_CURRENT_TEST` (y la variable
`SQLITEPLUS_FORCE_RESET`) cada vez que necesita crear una conexión. De este modo puedes activar el
modo limpieza incluso si el objeto global ya estaba instanciado o si quieres forzar el borrado desde
la app FastAPI (por ejemplo, antes de lanzar un lote de pruebas de integración). Si la variable se
activa cuando ya existe una conexión viva en el mismo bucle, el gestor la cierra, elimina los ficheros
`*.db`, `*.db-wal` y `*.db-shm` y vuelve a levantar una base limpia. Usa valores como `1`, `true` o `on`
para activar `SQLITEPLUS_FORCE_RESET` y elimina la variable cuando dejes de necesitar el borrado
automático.

## Conexiones por bucle de eventos

Cuando se reutiliza el mismo nombre de base en distintos bucles de eventos (por ejemplo, al usar
`httpx.AsyncClient` en paralelo), el gestor cierra y recrea la conexión para ese bucle, evitando
errores de "conexión ligada a otro loop".

## Aplicar SQLCipher solo si existe clave

Si `SQLITE_DB_KEY` está vacío, la API trabaja sin cifrado. Al definir la variable se ejecuta
`PRAGMA key` y se propagan los posibles errores de SQLCipher en los logs.

## Replicación y exportaciones automatizadas

El módulo `sqliteplus.utils.replication_sync.SQLiteReplication` permite:

- `backup_database()` – genera copias fechadas y duplica ficheros WAL/SHM si existen.
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
