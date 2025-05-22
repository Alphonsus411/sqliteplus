# Configuración Avanzada

## Variables de entorno

- `SECRET_KEY`: Clave JWT
- `SQLITE_DB_KEY`: Clave de cifrado para SQLCipher
- `REDIS_HOST`, `REDIS_PORT`: Datos de conexión a Redis

## Lifespan y cierre de conexiones

FastAPI cierra automáticamente las conexiones al apagar el servidor gracias al manejador `lifespan`.
