"""Ajustes de pruebas para exponer compatibilidades de sqliteplus."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from sqliteplus._compat import ensure_bcrypt

ensure_bcrypt()
