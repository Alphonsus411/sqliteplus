# Casos de uso avanzados

## Reinicialización automática en pruebas

`AsyncDatabaseManager` detecta la variable `PYTEST_CURRENT_TEST` y elimina automáticamente la
base temporal antes de cada suite, evitando datos residuales entre ejecuciones.

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

## Actualización caliente de usuarios

`sqliteplus.auth.users.get_user_service()` mantiene una caché basada en la firma del archivo. Al
modificar `SQLITEPLUS_USERS_FILE` se detecta el cambio automáticamente y se recarga la lista de
usuarios sin reiniciar el proceso.
