"""Utilidades de compatibilidad para dependencias opcionales."""

from __future__ import annotations

if __name__ == "__main__" and __package__ in {None, ""}:
    import sys
    from pathlib import Path
    from runpy import run_module

    package_root = Path(__file__).resolve().parents[2]
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    run_module("sqliteplus._compat.__init__", run_name="__main__")
    raise SystemExit()

from sqliteplus._compat.bootstrap import ensure_bcrypt

__all__ = ["ensure_bcrypt"]
