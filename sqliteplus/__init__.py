"""Utilidades del paquete sqliteplus."""

from __future__ import annotations

from importlib import metadata as importlib_metadata

_PACKAGE_NAME = "sqliteplus-enhanced"
_FALLBACK_VERSION = "0.0.0-dev"

try:  # pragma: no cover - depende del entorno de instalación
    __version__ = importlib_metadata.version(_PACKAGE_NAME)
except importlib_metadata.PackageNotFoundError:  # pragma: no cover - ruta de desarrollo
    __version__ = _FALLBACK_VERSION

__all__ = ["__version__"]
