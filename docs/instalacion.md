# Instalación

## Requisitos previos

- Python 3.10 o superior.
- SQLite con modo WAL habilitado (viene activado por defecto en SQLite moderno).
- Opcional: Redis (planificado en versiones futuras; actualmente no se distribuye una capa de caché integrada).

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

## Desde PyPI

```bash
pip install sqliteplus-enhanced
```

La distribución incluye el comando `sqliteplus` y el paquete `sqliteplus.main` listo para ejecutarse con Uvicorn.
