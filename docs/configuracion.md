# Configuración avanzada

## Variables de entorno soportadas

| Variable | Descripción |
| --- | --- |
| `HOME` | Utilizada al expandir rutas con `~` en `SQLITEPLUS_USERS_FILE`. |
| `PYTEST_CURRENT_TEST` | Detectada automáticamente por pytest para reiniciar bases temporales. |
| `SECRET_KEY` | Clave obligatoria para firmar y validar los JWT emitidos por la API. Se comprueba en tiempo de ejecución. |
| `SQLITEPLUS_FORCE_RESET` | Solicita la reinicialización de las bases (valores `1`, `true` o `on`) **solo** cuando el entorno es seguro (`SQLITEPLUS_ENV=test` o `PYTEST_CURRENT_TEST`). Fuera de ese contexto se ignora y se emite un warning en logs. |
| `SQLITEPLUS_ALLOW_WEAK_USERS_FILE_PERMS` | Permite cargar archivos `SQLITEPLUS_USERS_FILE` con permisos POSIX débiles (grupo/otros). Úsalo solo para compatibilidad legacy (`1`) y con warnings explícitos en logs. |
| `SQLITEPLUS_USERS_FILE` | Ruta (admite `~`) del archivo JSON con usuarios y hashes `bcrypt`. Solo es obligatorio al exponer la API/autenticación. |
| `SQLITE_DB_KEY` | Clave SQLCipher opcional. Si no existe, se omite el cifrado. |

## Directorios de trabajo

- Las bases asincrónicas se almacenan en la carpeta `databases/` por defecto.
- Las copias de seguridad generadas por la CLI residen en `backups/`.
- `SQLiteReplication` copia los archivos `-wal` y `-shm` asociados para mantener la integridad.

## Opciones de la CLI

- `--cipher-key` / `SQLITE_DB_KEY`: permite usar SQLCipher en las operaciones sincrónicas.
- Los subcomandos `export-csv` y `backup` aceptan rutas personalizadas conservando nombres seguros.

## Autenticación externa

El archivo apuntado por `SQLITEPLUS_USERS_FILE` debe tener la estructura:

```json
{
  "admin": "$2b$12$..."
}
```

Puedes generar nuevos hashes con el módulo `bcrypt` desde Python, tal como se muestra en la guía de
uso básico.

En plataformas POSIX también se valida que el archivo no tenga permisos excesivos para grupo/otros.
Se recomienda aplicar `chmod 600 /ruta/a/users.json` antes de arrancar la API. Si necesitas permitir
temporalmente permisos más débiles por motivos legacy, define `SQLITEPLUS_ALLOW_WEAK_USERS_FILE_PERMS=1`
y revisa los warnings emitidos en logs.
