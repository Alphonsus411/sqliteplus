"""Arranque de compatibilidad con dependencias opcionales."""
from __future__ import annotations

import importlib
import importlib.util
import sys
from types import ModuleType
from typing import Final

_FALLBACK_MODULE: Final[str] = "sqliteplus._compat.bcrypt"


def _load_real_bcrypt() -> ModuleType | None:
    """Intenta cargar la implementación real de ``bcrypt`` si está disponible."""

    spec = importlib.util.find_spec("bcrypt")
    if spec is None:
        return None
    module = importlib.import_module("bcrypt")
    return module


def ensure_bcrypt() -> ModuleType:
    """Garantiza que :mod:`bcrypt` esté disponible, usando un *fallback* si hace falta."""

    existing = sys.modules.get("bcrypt")
    if existing is not None:
        return existing

    real_module = _load_real_bcrypt()
    if real_module is not None:
        sys.modules.setdefault("bcrypt", real_module)
        return real_module

    fallback = importlib.import_module(_FALLBACK_MODULE)
    sys.modules.setdefault("bcrypt", fallback)
    return fallback
