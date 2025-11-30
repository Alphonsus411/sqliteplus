from __future__ import annotations

if __name__ == "__main__" and __package__ in {None, ""}:
    import sys
    from pathlib import Path
    from runpy import run_module

    package_root = Path(__file__).resolve().parents[2]
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    run_module("sqliteplus.utils.replication_sync", run_name="__main__")
    raise SystemExit()

import importlib.machinery
import importlib.util
import sys
from pathlib import Path
from types import ModuleType

from sqliteplus.utils.constants import DEFAULT_DB_PATH, PACKAGE_DB_PATH

__all__ = ["SQLiteReplication", "PACKAGE_DB_PATH", "DEFAULT_DB_PATH"]


def _load_cython_variant() -> ModuleType | None:
    """Carga el módulo C si está disponible junto a este archivo."""

    if __name__ == "__main__":
        return None

    module_path = Path(__file__)
    for suffix in importlib.machinery.EXTENSION_SUFFIXES:
        candidate = module_path.with_suffix(suffix)
        if candidate.exists():
            spec = importlib.util.spec_from_file_location(__name__, candidate)
            if spec and spec.loader:
                module = importlib.util.module_from_spec(spec)
                sys.modules[__name__] = module
                spec.loader.exec_module(module)
                return module
    return None


_cython_module = _load_cython_variant()
if _cython_module is not None:
    globals().update(_cython_module.__dict__)
else:
    from sqliteplus.utils._replication_sync_py import *
