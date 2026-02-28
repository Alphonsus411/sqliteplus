[Read in English](en/changelog.md)

# Resumen del historial de cambios

Esta página resume los principales hitos publicados en el proyecto. Para revisar el detalle completo consulta el [CHANGELOG en GitHub](https://github.com/Alphonsus411/sqliteplus-enhanced/blob/main/CHANGELOG.md).

## Unreleased
- _Sin entradas por ahora._

## 1.0.9 · 2025-11-14
- CLI renovada con comandos de inspección (`list-tables`, `describe-table`, `db-info`) y paneles FletPlus para explorar la base.
- Tablas y paneles enriquecidos con Rich, junto a métodos síncronos que replican las operaciones de la CLI y mejoran la salida de `fetch`.
- Validaciones adicionales en nombres y rutas de bases/usuarios, reorganización de extras (`dev`, `redis`) y parches de seguridad en dependencias críticas.

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
- Correcciones en el servidor asíncrono (actualmente en `sqliteplus/core/db.py`) para soportar múltiples clientes simultáneos.
- Nota: tras la refactorización de la versión 1.0.4 la funcionalidad de `server_async.py` se consolidó en `sqliteplus/core/db.py` para mantener un único gestor.

## 1.0.0 · 2025-03-02
- Prototipo inicial de SQLitePlus basado en FastAPI.
