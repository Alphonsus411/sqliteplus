# CLI `sqliteplus`

El paquete instala el comando `sqliteplus`, pensado para quienes prefieren gestionar la base sin levantar la API. El comando principal acepta dos opciones globales:

- `--cipher-key` (o la variable `SQLITE_DB_KEY`) para abrir bases cifradas.
- `--db-path` para indicar qué archivo `.db` usarán los subcomandos.

## Inicializar la base

```bash
sqliteplus init-db
```

Si la base no existe se crea automáticamente y se anota la acción en la tabla `logs`. El mensaje de salida confirma la ruta final del archivo.

## Ejecutar consultas de escritura

```bash
sqliteplus execute INSERT INTO logs (action) VALUES ('Mensaje desde CLI')
```

El comando muestra un mensaje de éxito y, cuando hay una inserción, informa el último ID generado. Los errores de SQLite se convierten en mensajes claros de Click.

## Consultar información

```bash
sqliteplus fetch SELECT * FROM logs
```

Los resultados aparecen fila a fila. Si la consulta no devuelve datos el programa lo avisa para evitar confusiones.

## Exportar una tabla a CSV

```bash
sqliteplus export-csv logs logs.csv
```

Genera un CSV con encabezados listo para compartir. Si necesitas otra base diferente a la global, añade `--db-path /ruta/a/otra.db`.

## Crear copias de seguridad

```bash
sqliteplus backup
```

Obtendrás un respaldo fechado en la carpeta `backups/`. El comando indica el archivo final. También puedes pasar `--db-path` para copiar una base concreta.

## Trabajar con SQLCipher

```bash
sqliteplus --cipher-key "$SQLITE_DB_KEY" backup
```

Si la clave es incorrecta o el intérprete no soporta SQLCipher, la CLI mostrará un error fácil de entender para guiarte en la corrección.
