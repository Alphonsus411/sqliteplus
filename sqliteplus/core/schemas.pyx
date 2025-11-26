# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cdivision=True
"""Adaptadores en Cython para las funciones públicas de ``schemas.py``.

Estas funciones mantienen la misma API que sus equivalentes en Python, pero
reutilizan las implementaciones optimizadas ya disponibles en los módulos
``_schemas_fast`` y ``_schemas_columns`` para reducir sobrecarga durante la
validación de esquemas.
"""

from __future__ import annotations

cimport cython

from sqliteplus.core cimport _schemas_fast
from sqliteplus.core cimport _schemas_columns


@cython.cfunc
@cython.inline
def _to_bool(object value) -> cython.bint:
    """Convierte un resultado Python en ``bint`` sin validaciones extras."""

    return bool(value)


cpdef bint _py_is_valid_sqlite_identifier(str identifier):
    return _schemas_fast.is_valid_sqlite_identifier(identifier)


cpdef bint _py_has_balanced_parentheses(str expr):
    return _schemas_fast.has_balanced_parentheses(expr)


cpdef _py_parse_function_call(str expr):
    return _schemas_fast.parse_function_call(expr)


cpdef bint _py_is_safe_default_expr(str expr):
    return _to_bool(_schemas_columns.is_safe_default_expr(expr))


cpdef dict _py_normalized_columns(dict columns):
    return _schemas_columns.normalized_columns(columns)
