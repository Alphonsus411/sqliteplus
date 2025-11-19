# Instalación

## Requisitos previos

- Python 3.10 o superior.
- Una versión moderna de SQLite (el soporte para WAL viene incluido y el proyecto aplica `PRAGMA journal_mode=WAL` automáticamente).
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

> **Nota rápida:** No necesitas ninguna configuración manual adicional: el código fuerza `PRAGMA journal_mode=WAL` cada vez que abre una conexión (consulta `sqliteplus/core/db.py`).

Si aun así deseas preparar el entorno con las dependencias de Redis instala el extra:

```bash
pip install -e '.[redis]'
```

### Extra `visual`

La instalación principal ya incluye Rich, así que todas las tablas, paneles y mensajes de la CLI lucen correctamente sin pasos adicionales. El extra `visual` es opcional y añade únicamente las dependencias de los visores interactivos basados en FletPlus.

Instálalo solo si planeas usar los subcomandos o flags que abren esos visores (`sqliteplus fetch --viewer`, `sqliteplus list-tables --viewer`, `sqliteplus visual-dashboard`, etc.). Puedes consultar la [lista completa en docs/cli.md](cli.md#comandos-y-flags-que-requieren-el-extra-visual) para comprobar rápidamente si lo necesitas.

```bash
pip install -e '.[visual]'
```

> **Nota:** Consulta [docs/cli.md](cli.md) para revisar los comandos que requieren el extra `visual`.

## Desde PyPI

```bash
pip install sqliteplus-enhanced
```

> **Nota:** La integración con Redis está pendiente; instalar `sqliteplus-enhanced[redis]` solo añade las dependencias necesarias para futuras versiones. Consulta el [CHANGELOG](changelog.md) para conocer el estado actualizado.

Para incluir estas dependencias opcionales de Redis usa:

```bash
pip install 'sqliteplus-enhanced[redis]'
```

Para habilitar las capacidades visuales desde PyPI instala el extra correspondiente:

```bash
pip install "sqliteplus-enhanced[visual]"
```

> **Nota:** En [docs/cli.md](cli.md) encontrarás los comandos que dependen del extra `visual`.

> **Consejo:** Las comillas simples evitan que shells como `zsh` intenten expandir los corchetes, lo que podría generar errores al instalar los extras.

La distribución incluye el comando `sqliteplus` y el paquete `sqliteplus.main` listo para ejecutarse con Uvicorn.
