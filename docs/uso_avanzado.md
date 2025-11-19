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
exportación parta de un archivo sobre el que se puede escribir en el directorio de trabajo.

## Actualización caliente de usuarios

`sqliteplus.auth.users.get_user_service()` mantiene una caché basada en la firma del archivo. Al
modificar `SQLITEPLUS_USERS_FILE` se detecta el cambio automáticamente y se recarga la lista de
usuarios sin reiniciar el proceso.
