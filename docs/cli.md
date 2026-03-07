[Read in English](en/cli.md)

# CLI `sqliteplus`

El paquete instala el comando `sqliteplus`, pensado para quienes prefieren gestionar la base sin levantar la API. El comando principal acepta opciones globales de configuración y seguridad:

- `--cipher-key` (o la variable `SQLITE_DB_KEY`) para abrir bases cifradas.
- `--ask-key` para solicitar la clave de cifrado de forma interactiva y oculta, evitando que quede en el historial.
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

- Usa `--summary` para generar una tabla adicional con mínimos, máximos y promedios de las columnas numéricas.
- Con `--viewer` se abre un visor accesible construido con FletPlus; admite filtros en vivo, cambio de tema (`--viewer-theme`) y ajuste del tamaño del texto.
- Si necesitas paginar conjuntos grandes, combina `--viewer` con `--viewer-page-size` o `--viewer-virtual` para cargar filas bajo demanda.
- Cuando eliges `--output json`, cada valor de la consulta se normaliza antes de mostrarse: los BLOBs se codifican en Base64, los `Decimal` se convierten a números o cadenas y las fechas/horas se expresan en ISO 8601, evitando errores de serialización. Si la consulta devuelve columnas duplicadas, la salida adopta un objeto con `{"columns": [...], "rows": [...]}` para que ninguna posición se pierda al convertir a JSON.

> Para usar `--viewer` debes instalar el extra opcional `visual`: `pip install "sqliteplus-enhanced[visual]"`.

## Comandos y flags que requieren el extra `visual`

Los visores interactivos de FletPlus solo están disponibles cuando instalas el extra `visual`. Instálalo si necesitas alguno de
los siguientes flujos:

- `sqliteplus fetch --viewer`: habilita una cuadrícula interactiva donde también puedes combinar `--viewer-theme`, `--viewer-page-size` y `--viewer-virtual` para ajustar el aspecto y la paginación.
- `sqliteplus list-tables --viewer`: muestra un panel navegable para explorar tablas y vistas con filtros y ordenación.
- `sqliteplus visual-dashboard`: abre el panel completo de FletPlus y admite los flags `--theme`, `--accent-color` y `--max-rows` para personalizar el entorno.

### Listar tablas disponibles

```bash
sqliteplus list-tables
```

Muestra una tabla con todas las tablas de usuario y el número de filas registradas. Añade `--include-views` si también quieres ver las vistas definidas. Con `--viewer` obtienes un catálogo visual donde puedes ordenar y navegar por los objetos con ayuda de la última versión de FletPlus.

### Describir la estructura de una tabla

```bash
sqliteplus describe-table logs
```

Obtendrás un resumen con el número de filas, columnas, índices y claves foráneas de la tabla seleccionada.

### Ver estadísticas generales

```bash
sqliteplus db-info
```

Imprime la ruta del archivo activo, su tamaño en disco y el total de tablas, vistas y filas.

### Panel visual con FletPlus

```bash
sqliteplus visual-dashboard --theme dark --accent-color BLUE_200
```

Abre un panel enriquecido que aprovecha la nueva actualización de FletPlus. Puedes elegir el tema (`--theme`), personalizar el color primario (`--accent-color`) y navegar por vistas dedicadas a resumen, consultas, historial y ayudas de accesibilidad. Desde el propio panel es posible acceder a la paleta de comandos (Ctrl+K) o consultar los consejos incorporados.

> Este comando también requiere instalar el extra `visual` mediante `pip install "sqliteplus-enhanced[visual]"`.

#### Escenario manual: validar `max_rows` en `visual-dashboard`

1. Ejecuta `sqliteplus init-db` y crea una tabla con al menos 1 000 filas usando únicamente comandos compatibles con cualquier instalación base:

   ```bash
   sqliteplus execute "CREATE TABLE IF NOT EXISTS demo (id INTEGER PRIMARY KEY, note TEXT)"
   sqliteplus execute "WITH RECURSIVE counter(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM counter WHERE x < 1000) INSERT INTO demo(note) SELECT printf('fila %d', x) FROM counter"
   ```

2. Abre el panel con `sqliteplus visual-dashboard --max-rows 25` y dirígete a la pestaña de consultas.
3. Lanza `SELECT * FROM demo` sin cláusula `LIMIT`. El panel solo mostrará 25 filas y el mensaje inferior indicará que la consulta se truncó por el límite configurado.
4. Repite la consulta añadiendo `LIMIT 10` para comprobar que el mensaje cambia y ya no se advierte truncamiento.

> Si prefieres usar extensiones como `generate_series`, recuerda cargar explícitamente la extensión antes de ejecutar los ejemplos (`SELECT load_extension('mod_spatialite');`, etc.). El tutorial incluye instrucciones que funcionan sin extensiones para que puedas copiar y pegar los comandos en la CLI estándar de inmediato.

## Exportar una tabla a CSV

```bash
sqliteplus export-csv logs logs.csv
```

Genera un CSV con encabezados listo para compartir. Puedes utilizar nombres de tabla con espacios o guiones (`"logs con espacios"`, `"logs-con-guion"`), la herramienta se encarga de escaparlos sin perder seguridad. Si necesitas otra base diferente a la global, añade `--db-path /ruta/a/otra.db`.

De forma predeterminada, `export-csv` evita sobrescribir archivos ya existentes para que no pierdas datos accidentalmente. Si realmente deseas reemplazar el archivo, pasa el flag `--overwrite` y el comando continuará sin detenerse.

> Nota: la utilidad `SQLiteReplication.export_to_csv` únicamente devuelve la ruta final; la CLI se encarga de mostrarla en un panel Rich para evitar mensajes duplicados cuando reutilices la función desde tus propios scripts.

## Exportar resultados de una consulta

```bash
sqliteplus export-query --format json resultados.json "SELECT * FROM logs ORDER BY created_at DESC"
```

Permite ejecutar una consulta `SELECT` y guardar el resultado en un archivo JSON o CSV sin pasar por la API. Es útil para compartir subconjuntos filtrados o preparar datos para otras herramientas sin modificar la base.

- `--format` controla el formato de salida (`json` por defecto o `csv`).
- `--limit` restringe el número de filas exportadas sin alterar la consulta original.
- `--overwrite` habilita la sobrescritura del archivo de destino cuando ya existe.

Cuando eliges `--format json`, los valores especiales se transforman automáticamente para garantizar que el archivo pueda serializarse sin errores: los BLOBs y `memoryview` se codifican en Base64 con el prefijo `base64:`, los `Decimal` se convierten a números de punto flotante (o cadenas si exceden el rango) y las fechas/horas se expresan en ISO 8601. Además, si una columna carece de nombre o SQLite retorna una cadena vacía, el comando genera encabezados genéricos (`columna_1`, `columna_2`, etc.) para asegurar claves válidas en cada registro JSON.
En el caso de alias duplicados, la exportación crea un objeto con las claves `columns` y `rows` para preservar la estructura completa sin colisiones de nombres.

Si optas por CSV ocurre lo mismo: se respetan los nombres de columna provistos por la consulta, pero los huecos o celdas sin alias se sustituyen por esos identificadores automáticos, manteniendo la estructura tabular coherente.

```bash
sqliteplus export-query --format csv --limit 100 --overwrite resumen.csv \
  "SELECT level, COUNT(*) AS eventos FROM logs GROUP BY level ORDER BY level"
```

Cuando la consulta no devuelve nombres de columna o estos llegan vacíos (por ejemplo, al usar `SELECT '' AS ""` o expresiones similares), la CLI crea los encabezados `columna_n` para mantener una estructura coherente en el archivo final.
La misma convención `{"columns": [...], "rows": [...]}` se emplea si `fetch --output json` detecta duplicados, de modo que ambos comandos mantengan un formato compatible.

## Crear copias de seguridad

```bash
sqliteplus backup
```

Obtendrás un respaldo fechado en la carpeta `backups/`. El comando indica el archivo final. También puedes pasar `--db-path` para copiar una base concreta.

De forma análoga, `SQLiteReplication.backup_database` retorna la ubicación creada sin imprimir mensajes directos, lo que garantiza que toda la salida visible provenga de la CLI y puedas reutilizar la función en otros contextos.

## Trabajar con SQLCipher

Para mayor seguridad en entornos compartidos, evita pasar la clave directamente en el comando. Usa `--ask-key` para que la CLI te la solicite de forma oculta:

```bash
sqliteplus --ask-key backup
# Prompt: Clave de cifrado: ******
```

Si prefieres usar variables de entorno o scripts automatizados:

```bash
export SQLITE_DB_KEY="mi-secreto-seguro"
sqliteplus backup
```

La CLI detecta automáticamente si la clave es incorrecta o si la base requiere cifrado pero no se proporcionó ninguna credencial.

## Nuevo aspecto con Rich

Gracias a la librería [Rich](https://rich.readthedocs.io/en/stable/), todos los comandos muestran tablas, paneles y colores que facilitan la lectura, especialmente en pantallas oscuras o cuando necesitas compartir los resultados por terminal.
