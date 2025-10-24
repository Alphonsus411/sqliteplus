"""Configuración automática para disponibilizar dependencias opcionales."""
from sqliteplus._compat import ensure_bcrypt

# Garantiza que ``import bcrypt`` funcione incluso si la dependencia no está instalada.
ensure_bcrypt()
