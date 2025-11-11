# Changelog

Todas las versiones notables de `sqliteplus-enhanced`.

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/)
y semántica de versiones [SemVer](https://semver.org/lang/es/).

---

## [Unreleased]
### Añadido
- Comandos `list-tables`, `describe-table` y `db-info` para inspeccionar la base desde la CLI.
- Salida enriquecida con Rich (tablas, paneles y colores) para mejorar la accesibilidad.
- Métodos sincronizados para listar, describir y obtener estadísticas de la base de datos.

### Cambiado
- El comando `fetch` ahora muestra los resultados en tablas con formato y reporta el número de filas devueltas.
- Las dependencias de pruebas y herramientas se agruparon en el extra opcional `dev` del `pyproject.toml`.

---

## [1.0.7] - 2025-06-01
### Cambiado
- Documentación reescrita para reflejar el uso de `SQLITEPLUS_USERS_FILE`, el gestor asincrónico y la CLI `sqliteplus`.
- README actualizado con los nuevos flujos de instalación, configuración y pruebas.
- Guías MkDocs sincronizadas con las capacidades actuales de la librería (API, CLI, replicación y casos avanzados).

### Añadido
- Detalles operativos sobre la recarga de usuarios, reinicio automático de bases de datos en pruebas y soporte SQLCipher opcional.

---

## [1.0.4] - 2025-05-22
### Añadido
- Refactorización completa en arquitectura modular (`core/`, `api/`, `auth/`, `utils/`)
- CLI interactiva con `click` (`sqliteplus-enhanced`)
- API REST documentada con Swagger (FastAPI)
- Gestor asíncrono `AsyncDatabaseManager` con `aiosqlite`
- Autenticación JWT con `PyJWT`
- SQLCipher y Redis integrados en modo síncrono
- Tests de integración con `pytest-asyncio` y `httpx`
- Soporte para múltiples bases de datos en paralelo
- Exportación CSV y backups automáticos
- `pyproject.toml` + `setup.py` sincronizados para publicación en PyPI
- Pipeline de despliegue verificado en [pypi.org/project/sqliteplus-enhanced](https://pypi.org/project/sqliteplus-enhanced/)

---

## [1.0.3] - 2025-03-03
### Añadido
- Documentación inicial y README extendido
- Estructura básica de endpoints FastAPI

---

## [1.0.2] - 2025-03-03
### Corregido
- Corrección de errores en `server_async.py`
- Soporte para múltiples clientes simultáneos

---

## [1.0.0] - 2025-03-02
### Añadido
- Primer prototipo SQLitePlus con FastAPI
