[Leer en español](../changelog.md)

# Changelog Summary

This page summarizes the main milestones published in the project. To review the full detail, check the [CHANGELOG on GitHub](https://github.com/Alphonsus411/sqliteplus-enhanced/blob/main/CHANGELOG.md).

## Unreleased
- _No entries for now._

## 1.0.9 · 2025-11-14
- Renewed CLI with inspection commands (`list-tables`, `describe-table`, `db-info`) and FletPlus panels to explore the database.
- Tables and panels enriched with Rich, along with synchronous methods that replicate CLI operations and improve `fetch` output.
- Additional validations on names and database/user paths, reorganization of extras (`dev`, `redis`), and security patches in critical dependencies.

## 1.0.7 · 2025-06-01
- General documentation updated to reflect configuration via `SQLITEPLUS_USERS_FILE` and new workflows.
- MkDocs guides synchronized with current library capabilities.
- Operational information on user reload, automatic restarts, and optional SQLCipher support.

## 1.0.4 · 2025-05-22
- Modular architecture divided into `core/`, `api/`, `auth/`, and `utils/`.
- Interactive CLI, REST API with Swagger, and asynchronous manager based on `aiosqlite`.
- SQLCipher integration, multi-database support, CSV exports/backups, and PyPI publication pipeline.

## 1.0.3 · 2025-03-03
- Initial documentation and README expansion.
- First version of FastAPI endpoints.

## 1.0.2 · 2025-03-03
- Fixes in the asynchronous server (currently in `sqliteplus/core/db.py`) to support multiple simultaneous clients.
- Note: after the 1.0.4 refactor, `server_async.py` functionality was consolidated into `sqliteplus/core/db.py` to maintain a single manager.

## 1.0.0 · 2025-03-02
- Initial prototype of SQLitePlus based on FastAPI.
