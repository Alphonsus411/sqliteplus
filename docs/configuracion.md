# Configuración Avanzada

## Variables de entorno

- `SECRET_KEY`: Clave JWT
- `SQLITE_DB_KEY`: Clave de cifrado para SQLCipher
- `REDIS_HOST`, `REDIS_PORT`: Datos de conexión a Redis

## Lifespan y cierre de conexiones

FastAPI cierra automáticamente las conexiones al apagar el servidor gracias al manejador `lifespan`.

## CLI y SQLCipher

El comando `sqliteplus` detecta automáticamente la variable de entorno `SQLITE_DB_KEY`.
También puedes especificar la clave manualmente con `--cipher-key` en cada subcomando,
lo que resulta útil para scripts de respaldo o replicación programados.
