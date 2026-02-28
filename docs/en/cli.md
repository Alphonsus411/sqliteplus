[Leer en español](../cli.md)

# `sqliteplus` CLI

The package installs the `sqliteplus` command, designed for those who prefer managing the database without starting the API. The main command accepts two global options:

- `--cipher-key` (or the `SQLITE_DB_KEY` variable) to open encrypted databases.
- `--db-path` to indicate which `.db` file the subcommands will use.

## Initialize the database

```bash
sqliteplus init-db
```

If the database does not exist, it is created automatically, and the action is logged in the `logs` table. The output confirms the final file path.

## Execute write queries

```bash
sqliteplus execute "INSERT INTO logs (action) VALUES ('Message from CLI')"
```

The command shows a success message and, when there is an insertion, reports the last generated ID. SQLite errors are converted into clear Click messages.

## Query information

```bash
sqliteplus fetch "SELECT * FROM logs"
```

Results appear row by row. If the query returns no data, the program warns you to avoid confusion.

- Use `--summary` to generate an additional table with minimums, maximums, and averages for numeric columns.
- With `--viewer`, an accessible viewer built with FletPlus opens; it supports live filters, theme changes (`--viewer-theme`), and text size adjustment.
- If you need to paginate large sets, combine `--viewer` with `--viewer-page-size` or `--viewer-virtual` to load rows on demand.
- When choosing `--output json`, each value is normalized before display: BLOBs are Base64 encoded, `Decimal` converted to numbers or strings, and dates/times expressed in ISO 8601. If the query returns duplicate columns, the output adopts an object with `{"columns": [...], "rows": [...]}` so no position is lost.

> To use `--viewer`, you must install the optional `visual` extra: `pip install "sqliteplus-enhanced[visual]"`.

## Commands and flags requiring the `visual` extra

FletPlus interactive viewers are only available when you install the `visual` extra. Install it if you need any of the following flows:

- `sqliteplus fetch --viewer`: enables an interactive grid where you can also combine `--viewer-theme`, `--viewer-page-size`, and `--viewer-virtual`.
- `sqliteplus list-tables --viewer`: shows a navigable panel to explore tables and views with filters and sorting.
- `sqliteplus visual-dashboard`: opens the full FletPlus dashboard and supports `--theme`, `--accent-color`, and `--max-rows` flags.

### List available tables

```bash
sqliteplus list-tables
```

Shows a table with all user tables and the number of rows recorded. Add `--include-views` if you also want to see defined views. With `--viewer`, you get a visual catalog to sort and navigate objects with the latest FletPlus version.

### Describe table structure

```bash
sqliteplus describe-table logs
```

You will get a summary with the number of rows, columns, indexes, and foreign keys of the selected table.

### View general statistics

```bash
sqliteplus db-info
```

Prints the active file path, its size on disk, and the total tables, views, and rows.

### Visual Dashboard with FletPlus

```bash
sqliteplus visual-dashboard --theme dark --accent-color BLUE_200
```

Opens an enriched dashboard leveraging the new FletPlus update. You can choose the theme (`--theme`), customize the primary color (`--accent-color`), and navigate through views dedicated to summary, queries, history, and accessibility aids. From the dashboard itself, it is possible to access the command palette (Ctrl+K) or consult built-in tips.

> This command also requires installing the `visual` extra via `pip install "sqliteplus-enhanced[visual]"`.

#### Manual Scenario: Validate `max_rows` in `visual-dashboard`

1. Run `sqliteplus init-db` and create a table with at least 1,000 rows using only standard commands:

   ```bash
   sqliteplus execute "CREATE TABLE IF NOT EXISTS demo (id INTEGER PRIMARY KEY, note TEXT)"
   sqliteplus execute "WITH RECURSIVE counter(x) AS (SELECT 1 UNION ALL SELECT x + 1 FROM counter WHERE x < 1000) INSERT INTO demo(note) SELECT printf('row %d', x) FROM counter"
   ```

2. Open the dashboard with `sqliteplus visual-dashboard --max-rows 25` and go to the query tab.
3. Launch `SELECT * FROM demo` without a `LIMIT` clause. The dashboard will only show 25 rows, and the bottom message will indicate the query was truncated by the configured limit.
4. Repeat the query adding `LIMIT 10` to verify the message changes and no longer warns about truncation.

## Export a table to CSV

```bash
sqliteplus export-csv logs logs.csv
```

Generates a CSV with headers ready to share. You can use table names with spaces or hyphens; the tool handles escaping them securely. If you need a different database than the global one, add `--db-path /path/to/other.db`.

By default, `export-csv` avoids overwriting existing files. If you really want to replace the file, pass the `--overwrite` flag.

## Export query results

```bash
sqliteplus export-query --format json results.json "SELECT * FROM logs ORDER BY created_at DESC"
```

Allows executing a `SELECT` query and saving the result to a JSON or CSV file without going through the API.

- `--format` controls the output format (`json` by default or `csv`).
- `--limit` restricts the number of exported rows.
- `--overwrite` enables overwriting the destination file.

When choosing `--format json`, special values are automatically transformed: BLOBs and `memoryview` are Base64 encoded with prefix `base64:`, `Decimal` converted to float (or strings if out of range), and dates/times expressed in ISO 8601.

If duplicate aliases exist, the export creates an object with `columns` and `rows` keys.

```bash
sqliteplus export-query --format csv --limit 100 --overwrite summary.csv \
  "SELECT level, COUNT(*) AS events FROM logs GROUP BY level ORDER BY level"
```

## Create backups

```bash
sqliteplus backup
```

You will get a dated backup in the `backups/` folder. The command indicates the final file. You can also pass `--db-path`.

## Working with SQLCipher

```bash
sqliteplus --cipher-key "$SQLITE_DB_KEY" backup
```

If the key is incorrect or the interpreter does not support SQLCipher, the CLI will show an easy-to-understand error.

## New Look with Rich

Thanks to the [Rich](https://rich.readthedocs.io/en/stable/) library, all commands show tables, panels, and colors that facilitate reading.
