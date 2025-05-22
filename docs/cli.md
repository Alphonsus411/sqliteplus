## CLI - Interfaz de Línea de Comandos

SQLitePlus Enhanced ofrece una CLI sencilla para ejecutar acciones rápidas sobre tu base de datos.

---

## 📦 Inicializar la base de datos

```bash
sqliteplus-enhanced init-db
```
Crea el archivo database.db y registra el log de inicialización.

## 🛠 Ejecutar consulta de escritura

```bash
sqliteplus-enhanced execute "INSERT INTO logs (msg) VALUES ('Mensaje desde CLI')"
```

Inserta directamente un registro o ejecuta cualquier consulta de escritura.

## 🔎 Ejecutar consulta de lectura

````bash
sqliteplus-enhanced fetch "SELECT * FROM logs"
````

Devuelve y muestra el resultado de cualquier consulta SELECT.

## 🧾 Exportar tabla a CSV

````bash
sqliteplus-enhanced export-csv logs salida.csv
````

Guarda los datos de la tabla logs en un archivo CSV llamado salida.csv

## 💾 Crear copia de seguridad

````bash
sqliteplus-enhanced backup
````
Genera una copia en la carpeta backups/ con fecha y hora.

## ℹ️ Ayuda

````bash
sqliteplus-enhanced --help
````