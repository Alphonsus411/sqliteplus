# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cdivision=True
"""Rutinas en Cython para normalizar columnas y validar expresiones DEFAULT."""

from __future__ import annotations

cimport cython

from sqliteplus.core cimport _schemas_fast

import re

SQLITE_IDENTIFIER_PATTERN = re.compile(r"^(?!\s)(?!.*\s$)[^\"\x00-\x1F]+$")

_ALLOWED_BASE_TYPES = {"INTEGER", "TEXT", "REAL", "BLOB", "NUMERIC"}
_DEFAULT_EXPR_NUMERIC_PATTERN = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
_DEFAULT_EXPR_STRING_PATTERN = re.compile(r"^'(?:''|[^'])*'$")
_DEFAULT_EXPR_ALLOWED_LITERALS = {"NULL", "TRUE", "FALSE"}
_DEFAULT_EXPR_ALLOWED_FUNCTIONS = {
    "CURRENT_TIMESTAMP",
    "CURRENT_DATE",
    "CURRENT_TIME",
    "DATE",
    "TIME",
    "DATETIME",
    "JULIANDAY",
    "STRFTIME",
    "STRIP",
    "LOWER",
    "UPPER",
    "HEX",
    "QUOTE",
    "RAISE",
    "ABS",
    "RANDOM",
    "ROUND",
    "LENGTH",
    "SUBSTR",
    "TRIM",
    "COALESCE",
    "NULLIF",
    "IFNULL",
    "PRINTF",
}
_DEFAULT_EXPR_DISALLOWED_TOKENS = (";", "--", "/*", "*/", " PRAGMA ")
_DEFAULT_EXPR_DISALLOWED_KEYWORDS = (
    " ATTACH ",
    " DETACH ",
    " SELECT ",
    " DROP ",
    " DELETE ",
    " INSERT ",
    " UPDATE ",
    " ALTER ",
    " CREATE ",
    " PRAGMA ",
)


@cython.cfunc
@cython.inline
def _has_disallowed_identifier_tokens(str name) -> cython.bint:
    for token in _schemas_fast.SQLITE_IDENTIFIER_DISALLOWED_TOKENS:
        if token in name:
            return True
    return False


@cython.cfunc
def _sanitize_default_expr(
    str rest_upper, str rest_original, Py_ssize_t expr_start, Py_ssize_t length, str raw_name
):
    cdef Py_ssize_t keyword_pos
    cdef Py_ssize_t expr_end = length
    for keyword in (" NOT NULL", " UNIQUE", " PRIMARY KEY", " DEFAULT"):
        keyword_pos = rest_upper.find(keyword, expr_start)
        if keyword_pos != -1 and keyword_pos < expr_end:
            expr_end = keyword_pos

    default_expr = rest_original[expr_start:expr_end].strip()
    if not default_expr:
        raise ValueError(f"Expresión DEFAULT inválida para columna '{raw_name}'")
    return default_expr, expr_end


@cython.cfunc
def _append_default_expr(list normalized_parts, str default_expr, str raw_name):
    if not is_safe_default_expr(default_expr):
        raise ValueError(
            f"Expresión DEFAULT potencialmente insegura para columna '{raw_name}'"
        )
    normalized_parts.append(f"DEFAULT {default_expr}")


@cython.cfunc
def _parse_constraints(str rest_upper, str rest_original, str raw_name, str raw_type):
    cdef cython.bint not_null = False
    cdef cython.bint unique = False
    cdef cython.bint primary_key = False
    cdef cython.bint autoincrement = False
    cdef str default_expr = None

    cdef Py_ssize_t idx = 0
    cdef Py_ssize_t length = len(rest_upper)
    cdef Py_ssize_t expr_start

    while idx < length:
        if rest_upper[idx] == " ":
            idx += 1
            continue

        if rest_upper.startswith("NOT NULL", idx):
            if not_null:
                raise ValueError(f"Restricción repetida para columna '{raw_name}': NOT NULL")
            not_null = True
            idx += len("NOT NULL")
            continue

        if rest_upper.startswith("UNIQUE", idx):
            if unique:
                raise ValueError(f"Restricción repetida para columna '{raw_name}': UNIQUE")
            unique = True
            idx += len("UNIQUE")
            continue

        if rest_upper.startswith("PRIMARY KEY", idx):
            if primary_key:
                raise ValueError(f"Restricción repetida para columna '{raw_name}': PRIMARY KEY")
            primary_key = True
            idx += len("PRIMARY KEY")
            if idx < length and rest_upper.startswith(" AUTOINCREMENT", idx):
                if autoincrement:
                    raise ValueError(
                        f"Restricción repetida para columna '{raw_name}': AUTOINCREMENT"
                    )
                autoincrement = True
                idx += len(" AUTOINCREMENT")
            continue

        if rest_upper.startswith("DEFAULT", idx):
            if default_expr is not None:
                raise ValueError(f"Restricción repetida para columna '{raw_name}': DEFAULT")

            expr_start = idx + len("DEFAULT")
            while expr_start < length and rest_upper[expr_start] == " ":
                expr_start += 1

            default_expr, idx = _sanitize_default_expr(
                rest_upper, rest_original, expr_start, length, raw_name
            )
            continue

        raise ValueError(f"Restricción no permitida para columna '{raw_name}': {raw_type}")

    return not_null, unique, primary_key, autoincrement, default_expr


cpdef dict normalized_columns(dict columns):
    """Valida y normaliza los nombres y tipos de columna permitidos."""

    if not columns:
        raise ValueError("Se requiere al menos una columna para crear la tabla")

    cdef dict sanitized_columns = {}
    cdef set seen_names = set()
    cdef object raw_name
    cdef object raw_type
    cdef str normalized_name
    cdef str normalized_key
    cdef str normalized_original
    cdef str base_original
    cdef str rest_original
    cdef str rest_upper
    cdef list normalized_parts

    for raw_name, raw_type in columns.items():
        normalized_name = raw_name.strip()
        if not normalized_name:
            raise ValueError("Los nombres de columna no pueden estar vacíos")

        if not SQLITE_IDENTIFIER_PATTERN.match(normalized_name):
            raise ValueError(f"Nombre de columna inválido: {raw_name}")

        if _has_disallowed_identifier_tokens(normalized_name):
            raise ValueError(f"Nombre de columna inválido: {raw_name}")

        normalized_key = normalized_name.casefold()
        if normalized_key in seen_names:
            raise ValueError(f"Nombre de columna duplicado tras normalización: {normalized_name}")
        seen_names.add(normalized_key)

        normalized_original = " ".join(raw_type.strip().split())
        if not normalized_original:
            raise ValueError(f"Tipo de columna vacío para '{raw_name}'")

        base_original, *rest_tokens = normalized_original.split(" ")
        base = base_original.upper()
        if base not in _ALLOWED_BASE_TYPES:
            raise ValueError(f"Tipo de dato no permitido para '{raw_name}': {raw_type}")

        rest_original = " ".join(rest_tokens)
        rest_upper = rest_original.upper()

        not_null, unique, primary_key, autoincrement, default_expr = _parse_constraints(
            rest_upper, rest_original, raw_name, raw_type
        )

        if autoincrement and base != "INTEGER":
            raise ValueError(f"AUTOINCREMENT solo es válido en columnas INTEGER: {raw_type}")

        if autoincrement and not primary_key:
            raise ValueError(f"AUTOINCREMENT requiere PRIMARY KEY en la columna '{raw_name}'")

        normalized_parts = [base]
        if primary_key:
            normalized_parts.append("PRIMARY KEY")
            if autoincrement:
                normalized_parts.append("AUTOINCREMENT")
        if not_null:
            normalized_parts.append("NOT NULL")
        if unique:
            normalized_parts.append("UNIQUE")
        if default_expr is not None:
            _append_default_expr(normalized_parts, default_expr, raw_name)

        sanitized_columns[normalized_name] = " ".join(normalized_parts)

    return sanitized_columns


cpdef bint is_safe_default_expr(str expr):
    sanitized = _schemas_fast.strip_enclosing_parentheses(expr.strip())
    upper = f" {sanitized.upper()} "

    for token in _DEFAULT_EXPR_DISALLOWED_TOKENS:
        if token in sanitized:
            return False

    for keyword in _DEFAULT_EXPR_DISALLOWED_KEYWORDS:
        if keyword in upper:
            return False

    if _DEFAULT_EXPR_NUMERIC_PATTERN.match(sanitized):
        return True

    if sanitized.upper() in _DEFAULT_EXPR_ALLOWED_LITERALS:
        return True

    if _DEFAULT_EXPR_STRING_PATTERN.match(sanitized):
        return True

    function_call = _schemas_fast.parse_function_call(sanitized)
    if function_call:
        func_name, _ = function_call
        if func_name.upper() in _DEFAULT_EXPR_ALLOWED_FUNCTIONS:
            return True

    return False
