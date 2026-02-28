[Read in English](en/configuration.md)

# Configuración avanzada

## Variables de entorno soportadas

| Variable | Descripción |
| --- | --- |
| `HOME` | Utilizada al expandir rutas con `~` en `SQLITEPLUS_USERS_FILE`. |
| `PYTEST_CURRENT_TEST` | Detectada automáticamente por pytest para reiniciar bases temporales. |
| `SECRET_KEY` | Clave obligatoria para firmar y validar los JWT emitidos por la API. Se comprueba en tiempo de ejecución. |
| `JWT_ISSUER` | Emisor (`iss`) de los JWT. Si está definido, se añade al token y también se valida al decodificar. |
| `JWT_AUDIENCE` | Audiencia (`aud`) de los JWT. Si está definida, se añade al token y también se valida al decodificar. |
| `JWT_STRICT_CLAIMS` | Activa modo estricto (`1`/`true`/`on`) para exigir `iss` y `aud` durante generación y validación. |
| `SQLITEPLUS_FORCE_RESET` | Solicita la reinicialización de las bases (valores `1`, `true` o `on`) **solo** cuando el entorno es seguro (`SQLITEPLUS_ENV=test` o `PYTEST_CURRENT_TEST`). Fuera de ese contexto se ignora y se emite un warning en logs. |
| `SQLITEPLUS_ALLOW_WEAK_USERS_FILE_PERMS` | Permite cargar archivos `SQLITEPLUS_USERS_FILE` con permisos POSIX débiles (grupo/otros). Úsalo solo para compatibilidad legacy (`1`) y con warnings explícitos en logs. |
| `SQLITEPLUS_USERS_FILE` | Ruta (admite `~`) del archivo JSON con usuarios y hashes `bcrypt`. Solo es obligatorio al exponer la API/autenticación. |
| `TRUSTED_PROXIES` | Lista separada por comas de IPs o CIDRs de proxies confiables (ej. `127.0.0.1,10.0.0.0/8`). **Por defecto está vacía** y no se confía en `Forwarded`/`X-Forwarded-For`. |
| `SQLITE_DB_KEY` | Clave SQLCipher. Si no se define, se usa modo texto plano. Si se define vacía, la API devuelve error 503 por seguridad. |

## Resolución de IP cliente detrás de proxy

El endpoint `POST /token` usa `REMOTE_ADDR` como fuente principal de IP cliente.

- Si `TRUSTED_PROXIES` **no** está definida (comportamiento por defecto), se ignoran
  las cabeceras `Forwarded` y `X-Forwarded-For`.
- Si `REMOTE_ADDR` coincide con alguna IP/red en `TRUSTED_PROXIES`, se permite usar
  `Forwarded` (prioridad) o `X-Forwarded-For` para identificar la IP original.

Esto evita que clientes externos falseen su IP cuando el servidor no está detrás de
un proxy explícitamente confiable.

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

## Migración de claims JWT (iss/aud)

Para facilitar transición sin romper clientes existentes, el comportamiento es gradual:

1. **Compatibilidad (por defecto):** si `JWT_STRICT_CLAIMS` no está activo, se emiten y validan
   `iss`/`aud` solo cuando `JWT_ISSUER`/`JWT_AUDIENCE` están definidos.
2. **Modo estricto recomendado:** define `JWT_STRICT_CLAIMS=1` junto con `JWT_ISSUER` y
   `JWT_AUDIENCE`. En este modo, un token sin esos claims se rechaza.
3. **Seguridad de firma HS256:** `SECRET_KEY` debe tener al menos 32 caracteres y una entropía
   básica (mezcla de categorías de caracteres y variedad suficiente).
