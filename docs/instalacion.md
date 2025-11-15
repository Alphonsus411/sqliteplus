# Instalación

## Requisitos previos

- Python 3.10 o superior.
- SQLite con modo WAL habilitado (viene activado por defecto en SQLite moderno).
- Opcional: Redis (la integración de caché está en desarrollo; consulta el [CHANGELOG](changelog.md) para conocer el estado actual del extra `redis`).

## Desde el repositorio

```bash
python -m venv .venv
source .venv/bin/activate
pip install -e .
```

Si vas a ejecutar las pruebas, el lint o contribuir con cambios instala también las dependencias opcionales y, a continuación, ejecuta la suite con Pytest:

```bash
pip install -e '.[dev]'
pytest -v
```

> **Nota:** La integración con Redis aún no está disponible en la aplicación. El extra `redis` únicamente instala las dependencias preliminares y puede cambiar en futuras versiones. Revisa el [CHANGELOG](changelog.md) para seguir el progreso.

Si aun así deseas preparar el entorno con las dependencias de Redis instala el extra:

```bash
pip install -e '.[redis]'
```

## Desde PyPI

```bash
pip install sqliteplus-enhanced
```

> **Nota:** La integración con Redis está pendiente; instalar `sqliteplus-enhanced[redis]` solo añade las dependencias necesarias para futuras versiones. Consulta el [CHANGELOG](changelog.md) para conocer el estado actualizado.

Para incluir estas dependencias opcionales de Redis usa:

```bash
pip install 'sqliteplus-enhanced[redis]'
```

> **Consejo:** Las comillas simples evitan que shells como `zsh` intenten expandir los corchetes, lo que podría generar errores al instalar los extras.

La distribución incluye el comando `sqliteplus` y el paquete `sqliteplus.main` listo para ejecutarse con Uvicorn.
