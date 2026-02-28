[Leer en español](../uso_avanzado.md)

# Advanced Usage

## Automatic Reinitialization in Tests

`AsyncDatabaseManager` detects the `PYTEST_CURRENT_TEST` variable and automatically removes the temporary database before each suite, avoiding residual data between runs. From this version onwards, the check is lazy: the manager re-reads `PYTEST_CURRENT_TEST`, `SQLITEPLUS_ENV`, and `SQLITEPLUS_FORCE_RESET` every time it needs to create a connection.

`SQLITEPLUS_FORCE_RESET` is only honored in a safe environment (`SQLITEPLUS_ENV=test` or `PYTEST_CURRENT_TEST` present). If attempted outside that context, the manager **does not delete files** and leaves an explicit warning in logs to avoid data loss in production.

If the variable is activated in a safe environment when there is already a live connection in the same loop, the manager closes it, deletes the `*.db`, `*.db-wal`, and `*.db-shm` files, and brings up a clean database.

To force a manual cleanup, there is the `reset_on_init=True` parameter, intended solely for tests and controlled migrations. Avoid using it in production flows.

## Connections per Event Loop

When the same database name is reused in different event loops (for example, when using `httpx.AsyncClient` in parallel), the manager closes and recreates the connection for that loop, avoiding "connection bound to a different loop" errors.

## Applying SQLCipher Only If Key Exists

If `SQLITE_DB_KEY` is not defined, the API works without encryption. If defined as an empty string, a 503 error is returned for security. When defining the variable with a non-empty value, `PRAGMA key` is executed, and possible SQLCipher errors are propagated in logs.

## Replication and Automated Exports

The `sqliteplus.utils.replication_sync.SQLiteReplication` module allows:

- `backup_database()` – generates dated backups and duplicates WAL/SHM files if they exist.
- `replicate_database(<path>)` – clones the database to another path applying the same SQLCipher key.
- `export_to_csv(<table>, <file>)` – exports columns and rows preserving field names.

From this version, instantiating `SQLiteReplication()` without arguments creates a local copy in `./sqliteplus/databases/database.db`, exactly as the CLI does. This prevents automated processes from modifying the installed package and ensures that any replication or export starts from a file that can be written to in the working directory. When the requested source is inside the package or is detected as non-writable, the module performs a byte-by-byte copy to the local directory (including `-wal`/`-shm` pairs). If the original database does not exist, the operation is aborted with a clear message instead of creating an empty file.

## Hot User Updates

`sqliteplus.auth.users.get_user_service()` maintains a cache based on the file signature. When modifying `SQLITEPLUS_USERS_FILE`, the change is automatically detected, and the user list is reloaded without restarting the process.

## CLI and API Profiling

To detect bottlenecks, you can launch controlled profiling with `cProfile` using the scenarios prepared in `tools/profile_sqliteplus.py`:

```bash
make profile PROFILE_SCENARIO=list_tables           # CLI: table inventory
make profile PROFILE_SCENARIO=db_info               # CLI: database summary
make profile PROFILE_SCENARIO=api_crud PROFILE_FLAGS="--include-io"
```

- Reports are saved in `reports/profile/<scenario>-<timestamp>.txt`.
- By default, common I/O functions (`sqlite3`, `socket`, `pathlib`, etc.) are omitted to highlight purely Python costs; add `--include-io` in `PROFILE_FLAGS` if you need the full picture.
- The **Top by cumulative time** block shows functions absorbing the most time, including internal calls; **Top by number of calls** helps detect paths executed excessively, even if lightweight.
- The **Highlighted pure Python functions** section lists only functions defined in `.py` modules, ideal for evaluating migrations to Cython or refactors: focus on those combining high cumulative time and many calls, especially if they belong to `sqliteplus` or auxiliary utilities not dependent on I/O.

## Cython Discovery and `.pyx` Twins

The Cython pipeline feeds on the dynamic list `reports/cython_candidates.json`. `setup.py` scans `sqliteplus/**/*.pyx` and, unless you define `SQLITEPLUS_IGNORE_CYTHON_TARGETS=1`, filters modules with that list. The recommended flow is:

1. Generate a hotspots report (e.g., `reports/hotspots.json`).
2. Run `tools/generate_cython_twins.py` to create `.pyx` twins and populate the candidates JSON:

   ```bash
   python tools/generate_cython_twins.py reports/hotspots.json --limit 3
   ```

   The script creates `.pyx` alongside each `.py` (e.g., `sqliteplus/core/validators.pyx`) and saves the final list in `reports/cython_candidates.json`. Use `--overwrite` if you need to regenerate existing files.

3. Launch the installation or build using the generated list:

   ```bash
   SQLITEPLUS_CYTHON_TARGETS=reports/cython_candidates.json python -m build
   ```

Useful variables to adjust behavior:

- `SQLITEPLUS_DISABLE_CYTHON=1` turns off compilation (pure Python mode).
- `SQLITEPLUS_FORCE_CYTHON=1` ignores lists and compiles all detected `.pyx`.
- `SQLITEPLUS_IGNORE_CYTHON_TARGETS=1` scans all `.pyx` but still respects `SQLITEPLUS_DISABLE_CYTHON`.
- `SQLITEPLUS_CYTHON_TARGETS=/other/list.json` points to an alternative JSON with allowed modules.
- `SQLITEPLUS_CYTHON_ANNOTATE=1` and `SQLITEPLUS_CYTHON_TRACE=1` generate annotation HTML and tracing macros in binaries.

To add a module manually, keep the original `.py` and add a `.pyx` twin in the same path that imports the `.py` as a *fallback*. If you need to expose types for `cimport`, accompany it with a `.pxd`. Include the new module in the candidates JSON or run with `SQLITEPLUS_FORCE_CYTHON=1` to compile it in a specific build. `sdist` includes `.py`, `.pyx`, and `.pxd`, and `wheel` publishes compiled binaries maintaining `.py` wrappers to preserve the API.
