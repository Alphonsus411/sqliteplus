# CLI `sqliteplus`

El paquete instala el comando `sqliteplus` mediante `setuptools`. Todas las opciones aceptan la
bandera global `--cipher-key` (o la variable `SQLITE_DB_KEY`).

## Inicializar la base

```bash
sqliteplus init-db
```

Crea `databases/default.db` y registra el log de inicialización.

## Ejecutar consultas

```bash
sqliteplus execute "INSERT INTO logs (action) VALUES ('Mensaje desde CLI')"
sqliteplus fetch "SELECT * FROM logs"
```

Los errores de SQLite se muestran como excepciones de Click amigables.

## Exportar a CSV

```bash
sqliteplus export-csv logs logs.csv
```

Genera un archivo CSV con encabezados. El nombre de la tabla se valida como identificador.

## Copia de seguridad

```bash
sqliteplus backup
```

Crea una copia fechada en `backups/` y replica los archivos `-wal/-shm` cuando existen.

## Uso con SQLCipher

```bash
sqliteplus --cipher-key "$SQLITE_DB_KEY" backup
```

Si la clave es incorrecta o el intérprete no soporta SQLCipher se mostrará un error descriptivo.
