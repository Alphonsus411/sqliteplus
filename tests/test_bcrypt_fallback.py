"""Pruebas unitarias para la implementación de compatibilidad de bcrypt."""

from __future__ import annotations

import importlib
import sys

import pytest


@pytest.fixture(autouse=True)
def _cleanup_bcrypt_modules():
    """Aísla los tests de cualquier módulo ``bcrypt`` real instalado."""

    previous = {name: module for name, module in sys.modules.items() if name.startswith("bcrypt")}
    for name in list(previous):
        sys.modules.pop(name, None)

    try:
        yield
    finally:
        for name in list(sys.modules):
            if name.startswith("bcrypt"):
                sys.modules.pop(name, None)
        sys.modules.update(previous)


def test_fallback_generates_and_verifies_hashes():
    """El módulo de compatibilidad debe generar hashes verificables."""

    compat = importlib.import_module("sqliteplus._compat.bcrypt")

    salt = compat.gensalt()
    assert salt.startswith(b"compatbcrypt$")

    hashed = compat.hashpw("secreto", salt)
    assert hashed.startswith(b"compatbcrypt$")

    assert compat.checkpw("secreto", hashed)
    assert not compat.checkpw("otro", hashed)


def test_public_shim_exposes_fallback_when_missing_real_module():
    """El paquete ``bcrypt`` integrado debe delegar en la versión compatible."""

    shim = importlib.import_module("bcrypt")

    salt = shim.gensalt()
    hashed = shim.hashpw("contraseña", salt)

    assert shim.checkpw("contraseña", hashed)
