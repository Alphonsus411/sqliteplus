# Instalación

## Requisitos previos

- Python 3.10 o superior.
- SQLite con modo WAL habilitado (viene activado por defecto en SQLite moderno).
- Opcional: Redis (solo necesario si deseas habilitar la caché; instálalo con el extra opcional `redis`).

## Desde el repositorio

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Si vas a ejecutar las pruebas, el lint o contribuir con cambios instala también las dependencias opcionales:

```bash
pip install -e .[dev]
```

Si también quieres preparar el entorno para integrar una caché con Redis instala el extra:

```bash
pip install -e .[redis]
```

## Desde PyPI

```bash
pip install sqliteplus-enhanced
```

Para incluir el soporte opcional de Redis usa:

```bash
pip install sqliteplus-enhanced[redis]
```

La distribución incluye el comando `sqliteplus` y el paquete `sqliteplus.main` listo para ejecutarse con Uvicorn.
