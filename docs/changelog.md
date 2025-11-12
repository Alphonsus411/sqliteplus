# Resumen del historial de cambios

Esta página resume los principales hitos publicados en el proyecto. Para revisar el detalle completo consulta el [CHANGELOG en GitHub](https://github.com/Alphonsus411/sqliteplus-enhanced/blob/main/CHANGELOG.md).

## Unreleased
- CLI enriquecida con comandos para inspeccionar la base (`list-tables`, `describe-table`, `db-info`).
- Salidas con formato usando Rich y soporte equivalente en los métodos síncronos.
- Ajustes en `fetch` y reorganización de dependencias opcionales en `pyproject.toml`.

## 1.0.7 · 2025-06-01
- Documentación general actualizada para reflejar la configuración mediante `SQLITEPLUS_USERS_FILE` y los nuevos flujos de trabajo.
- Guías de MkDocs sincronizadas con las capacidades actuales de la librería.
- Información operativa sobre recarga de usuarios, reinicios automáticos y soporte opcional para SQLCipher.

## 1.0.4 · 2025-05-22
- Arquitectura modular dividida en `core/`, `api/`, `auth/` y `utils/`.
- CLI interactiva, API REST con Swagger y gestor asíncrono basado en `aiosqlite`.
- Integración de SQLCipher, soporte multi-base de datos, exportaciones CSV/backups y pipeline de publicación en PyPI.

## 1.0.3 · 2025-03-03
- Documentación inicial y ampliación del README.
- Primera versión de los endpoints en FastAPI.

## 1.0.2 · 2025-03-03
- Correcciones en `server_async.py` para soportar múltiples clientes simultáneos.

## 1.0.0 · 2025-03-02
- Prototipo inicial de SQLitePlus basado en FastAPI.
