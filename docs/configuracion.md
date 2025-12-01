# Configuración avanzada

## Variables de entorno soportadas

| Variable | Descripción |
| --- | --- |
| `HOME` | Utilizada al expandir rutas con `~` en `SQLITEPLUS_USERS_FILE`. |
| `PYTEST_CURRENT_TEST` | Detectada automáticamente por pytest para reiniciar bases temporales. |
| `SECRET_KEY` | Clave obligatoria para firmar y validar los JWT emitidos por la API. Se comprueba en tiempo de ejecución. |
| `SQLITEPLUS_FORCE_RESET` | Fuerza la reinicialización de las bases sin depender de `PYTEST_CURRENT_TEST`. Admite `1`, `true` o `on`. La sección "Reinicialización automática en pruebas" de `docs/uso_avanzado.md` detalla el flujo. |
| `SQLITEPLUS_USERS_FILE` | Ruta (admite `~`) del archivo JSON con usuarios y hashes `bcrypt`. Solo es obligatorio al exponer la API/autenticación. |
| `SQLITE_DB_KEY` | Clave SQLCipher opcional. Si no existe, se omite el cifrado. |

## Directorios de trabajo

- Las bases asincrónicas se almacenan en la carpeta `databases/` por defecto.
- Las copias de seguridad generadas por la CLI residen en `backups/`.
- `SQLiteReplication` copia los ficheros `-wal` y `-shm` asociados para mantener la integridad.

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
