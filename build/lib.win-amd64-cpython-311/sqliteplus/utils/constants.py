"""Constantes compartidas del proyecto."""

from __future__ import annotations

from pathlib import Path

_RELATIVE_DB_PATH = Path("sqliteplus") / "databases" / "database.db"
_PACKAGE_ROOT = Path(__file__).resolve().parent.parent
PACKAGE_DB_PATH = _PACKAGE_ROOT / "databases" / "database.db"

# Ruta predeterminada expuesta públicamente. Se mantiene como cadena relativa para
# preservar la compatibilidad con código existente y la ayuda del CLI.
DEFAULT_DB_PATH = str(_RELATIVE_DB_PATH)


def resolve_default_db_path(*, prefer_package: bool = True) -> Path:
    """Devuelve la ruta predeterminada considerando el contexto de ejecución.

    Cuando ``prefer_package`` es ``True`` (comportamiento por defecto) se intenta
    utilizar la base de datos distribuida junto al paquete si existe. En caso
    contrario se devuelve la ruta relativa respecto al directorio de trabajo
    actual, permitiendo crear nuevas bases de datos locales en herramientas como
    el CLI.
    """

    local_candidate = Path.cwd() / _RELATIVE_DB_PATH
    if prefer_package and PACKAGE_DB_PATH.exists():
        return PACKAGE_DB_PATH
    return local_candidate


__all__ = ["DEFAULT_DB_PATH", "PACKAGE_DB_PATH", "resolve_default_db_path"]
