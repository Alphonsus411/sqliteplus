"""Compatibilidad integrada para la dependencia opcional :mod:`bcrypt`.

Este módulo intenta cargar la implementación real de :mod:`bcrypt` si está
disponible en el entorno. En caso contrario, expone una versión mínima basada
en :mod:`sqliteplus._compat.bcrypt` que implementa las funciones necesarias
para el proyecto y las pruebas automatizadas.

Contar con este *shim* evita depender de ``sitecustomize`` o de ajustes
externos del ``PYTHONPATH`` para registrar el módulo de compatibilidad, lo que
solucionaba errores de importación cuando la librería no estaba instalada.
"""

from __future__ import annotations

import importlib
import importlib.machinery
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from sqliteplus._compat import bcrypt as compat_bcrypt

__all__ = ["gensalt", "hashpw", "checkpw"]


def _load_system_bcrypt() -> ModuleType | None:
    """Intenta resolver la implementación real de :mod:`bcrypt`.

    Recorremos ``sys.path`` (excepto el primer elemento, que apunta al
    directorio actual y, por tanto, a este mismo módulo) buscando el módulo en
    los directorios del intérprete. Si se encuentra una implementación válida
    con ``PathFinder`` se carga y retorna.
    """

    current_file = Path(__file__).resolve()
    for entry in sys.path[1:]:
        try:
            spec = importlib.machinery.PathFinder.find_spec("bcrypt", [entry])
        except (ImportError, AttributeError):  # Entradas inválidas en sys.path
            continue

        if spec is None or spec.origin is None:
            continue

        origin_path = Path(spec.origin).resolve()
        if origin_path == current_file:
            # Se refiere a este mismo módulo; ignoramos para evitar recursiones.
            continue

        if spec.loader is None:
            continue

        module = importlib.util.module_from_spec(spec)
        previous = sys.modules.get("bcrypt")
        try:
            spec.loader.exec_module(module)
        except ModuleNotFoundError as exc:
            # Algunos entornos CI instalan ``bcrypt`` sin el módulo binario
            # ``_bcrypt``. En ese caso delegamos en la implementación de
            # compatibilidad en lugar de propagar el error y bloquear las
            # pruebas automatizadas.
            missing_ext = getattr(exc, "name", "")
            if missing_ext != "bcrypt._bcrypt":
                raise
            if previous is not None:
                sys.modules["bcrypt"] = previous
            else:
                sys.modules.pop("bcrypt", None)
            continue
        sys.modules["bcrypt"] = module
        return module

    return None


_system_module = _load_system_bcrypt()

if _system_module is not None:
    # Re-exportar los atributos de la implementación real.
    globals().update({name: getattr(_system_module, name) for name in dir(_system_module)})
else:
    # Fallback a la implementación pura en Python provista por sqliteplus.
    gensalt = compat_bcrypt.gensalt
    hashpw = compat_bcrypt.hashpw
    checkpw = compat_bcrypt.checkpw

