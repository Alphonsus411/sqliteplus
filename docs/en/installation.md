[Leer en español](../instalacion.md)

# Installation

## Prerequisites

- Python 3.10 or higher.
- A modern version of SQLite (WAL support is included and the project applies `PRAGMA journal_mode=WAL` automatically).
- Optional: Redis (cache integration is in development; check the [CHANGELOG](../changelog.md) for the current status of the `redis` extra).

## From the repository

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

If you are going to run tests, lint, or contribute with changes, also install the optional dependencies and then run the suite with Pytest:

```bash
pip install -e '.[dev]'
pytest -v
```

> **Note:** Redis integration is not yet available in the application. The `redis` extra only installs preliminary dependencies and may change in future versions. Check the [CHANGELOG](../changelog.md) to follow the progress.

> **Quick note:** You don't need any additional manual configuration: the code forces `PRAGMA journal_mode=WAL` every time it opens a connection (check `sqliteplus/core/db.py` and `sqliteplus/utils/sqliteplus_sync.py`).

If you still wish to prepare the environment with Redis dependencies, install the extra:

```bash
pip install -e '.[redis]'
```

### `visual` Extra

The main installation already includes Rich, so all tables, panels, and CLI messages look correct without additional steps. The `visual` extra is optional and only adds the dependencies for interactive viewers based on FletPlus.

Install it only if you plan to use the subcommands or flags that open those viewers (`sqliteplus fetch --viewer`, `sqliteplus list-tables --viewer`, `sqliteplus visual-dashboard`, etc.). You can check the [complete list in docs/cli.md](cli.md#commands-and-flags-requiring-visual-extra) to quickly verify if you need it.

```bash
pip install -e '.[visual]'
```

> **Note:** Check [docs/cli.md](cli.md) to review the commands that require the `visual` extra.

## From PyPI

```bash
pip install sqliteplus-enhanced
```

> **Note:** Redis integration is pending; installing `sqliteplus-enhanced[redis]` only adds the necessary dependencies for future versions. Check the [CHANGELOG](../changelog.md) for the updated status.

To include these optional Redis dependencies use:

```bash
pip install 'sqliteplus-enhanced[redis]'
```

To enable visual capabilities from PyPI install the corresponding extra:

```bash
pip install "sqliteplus-enhanced[visual]"
```

> **Note:** In [docs/cli.md](cli.md) you will find the commands that depend on the `visual` extra.

> **Tip:** Single quotes prevent shells like `zsh` from trying to expand the brackets, which could generate errors when installing extras.

The distribution includes the `sqliteplus` command and the `sqliteplus.main` package ready to run with Uvicorn.
