# Changelog

Todas las versiones notables de `sqliteplus-enhanced`.

Formato basado en [Keep a Changelog](https://keepachangelog.com/es/1.0.0/)
y semántica de versiones [SemVer](https://semver.org/lang/es/).

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
