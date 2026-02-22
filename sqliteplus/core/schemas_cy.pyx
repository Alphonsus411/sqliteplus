# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cdivision=True
"""Adaptadores y helpers acelerados para ``schemas.py``."""

cimport cython
from cpython.size_t cimport Py_ssize_t

from sqliteplus.core cimport _schemas_constants


cdef tuple _DISALLOWED_TOKENS = _schemas_constants.SQLITE_IDENTIFIER_DISALLOWED_TOKENS
cdef object _IDENTIFIER_PATTERN = _schemas_constants.SQLITE_IDENTIFIER_PATTERN
cdef object _FUNCTION_CALL_PATTERN = _schemas_constants.FUNCTION_CALL_PATTERN
cdef tuple _DEFAULT_DISALLOWED_TOKENS = _schemas_constants.DEFAULT_EXPR_DISALLOWED_TOKENS
cdef tuple _DEFAULT_DISALLOWED_KEYWORDS = _schemas_constants.DEFAULT_EXPR_DISALLOWED_KEYWORDS
cdef object _DEFAULT_NUMERIC_PATTERN = _schemas_constants.DEFAULT_EXPR_NUMERIC_PATTERN
cdef object _DEFAULT_STRING_PATTERN = _schemas_constants.DEFAULT_EXPR_STRING_PATTERN
cdef object _DEFAULT_LITERALS = _schemas_constants.DEFAULT_EXPR_ALLOWED_LITERALS
cdef object _DEFAULT_FUNCTIONS = _schemas_constants.DEFAULT_EXPR_ALLOWED_FUNCTIONS
cdef object _ALLOWED_BASE_TYPES = _schemas_constants.ALLOWED_BASE_TYPES


def _py_is_valid_sqlite_identifier(identifier):
    if not isinstance(identifier, str):
        return False

    cdef str ident = identifier
    cdef object token

    for token in _DISALLOWED_TOKENS:
        if token in ident:
            return False

    return bool(_IDENTIFIER_PATTERN.match(ident))


@cython.cfunc
def _has_balanced_parentheses_impl(str expr) -> cython.bint:
    cdef Py_ssize_t depth = 0
    cdef Py_ssize_t idx
    cdef Py_ssize_t length = len(expr)
    cdef str char

    for idx in range(length):
        char = expr[idx]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


cpdef bint _py_has_balanced_parentheses(str expr):
    return _has_balanced_parentheses_impl(expr)


cpdef str _py_strip_enclosing_parentheses(str expr):
    cdef str sanitized = expr
    cdef str inner

    while sanitized.startswith("(") and sanitized.endswith(")") and _has_balanced_parentheses_impl(sanitized):
        inner = sanitized[1 : len(sanitized) - 1].strip()
        if not inner:
            break
        sanitized = inner
    return sanitized


cpdef _py_parse_function_call(str expr):
    cdef object match = _FUNCTION_CALL_PATTERN.match(expr)
    if not match:
        return None

    cdef str func_name = match.group(1)
    cdef Py_ssize_t idx = match.end() - 1
    cdef Py_ssize_t depth = 0
    cdef Py_ssize_t pos
    cdef Py_ssize_t length = len(expr)
    cdef str char

    for pos in range(idx, length):
        char = expr[pos]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                if pos != length - 1:
                    return None
                args = expr[idx + 1 : pos].strip()
                return func_name, args
            if depth < 0:
                return None
    return None


cpdef bint _py_is_safe_default_expr(str expr):
    cdef str sanitized = _py_strip_enclosing_parentheses(expr.strip())
    cdef str upper = f" {sanitized.upper()} "

    cdef object token
    for token in _DEFAULT_DISALLOWED_TOKENS:
        if token in sanitized:
            return False

    for token in _DEFAULT_DISALLOWED_KEYWORDS:
        if token in upper:
            return False

    if _DEFAULT_NUMERIC_PATTERN.match(sanitized):
        return True

    if sanitized.upper() in _DEFAULT_LITERALS:
        return True

    if _DEFAULT_STRING_PATTERN.match(sanitized):
        return True

    cdef object function_call = _py_parse_function_call(sanitized)
    cdef str func_name
    if function_call:
        func_name = function_call[0]
        if func_name.upper() in _DEFAULT_FUNCTIONS:
            return True

    return False


def _py_normalized_columns(columns):
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
    cdef list rest_original_tokens
    cdef str base
    cdef str rest_original
    cdef str rest_upper
    cdef bint not_null
    cdef bint unique
    cdef bint primary_key
    cdef bint autoincrement
    cdef object default_expr
    cdef Py_ssize_t idx
    cdef Py_ssize_t length
    cdef Py_ssize_t expr_start
    cdef Py_ssize_t expr_end
    cdef list potential_ends
    cdef Py_ssize_t keyword_pos
    cdef list normalized_parts

    for raw_name, raw_type in columns.items():
        normalized_name = (<str>raw_name).strip()
        if not normalized_name:
            raise ValueError("Los nombres de columna no pueden estar vacíos")

        if not _IDENTIFIER_PATTERN.match(normalized_name):
            raise ValueError(f"Nombre de columna inválido: {raw_name}")

        if any(token in normalized_name for token in _DISALLOWED_TOKENS):
            raise ValueError(f"Nombre de columna inválido: {raw_name}")

        normalized_key = normalized_name.casefold()
        if normalized_key in seen_names:
            raise ValueError(
                f"Nombre de columna duplicado tras normalización: {normalized_name}"
            )
        seen_names.add(normalized_key)

        normalized_original = " ".join((<str>raw_type).strip().split())
        if not normalized_original:
            raise ValueError(f"Tipo de columna vacío para '{raw_name}'")

        rest_original_tokens = normalized_original.split(" ")
        base_original = rest_original_tokens[0]
        rest_original_tokens = rest_original_tokens[1:]
        base = base_original.upper()
        if base not in _ALLOWED_BASE_TYPES:
            raise ValueError(f"Tipo de dato no permitido para '{raw_name}': {raw_type}")

        rest_original = " ".join(rest_original_tokens)
        rest_upper = rest_original.upper()

        not_null = False
        unique = False
        primary_key = False
        autoincrement = False
        default_expr = None

        idx = 0
        length = len(rest_upper)
        while idx < length:
            if rest_upper[idx] == " ":
                idx += 1
                continue

            if rest_upper.startswith("NOT NULL", idx):
                if not_null:
                    raise ValueError(
                        f"Restricción repetida para columna '{raw_name}': NOT NULL"
                    )
                not_null = True
                idx += len("NOT NULL")
                continue

            if rest_upper.startswith("UNIQUE", idx):
                if unique:
                    raise ValueError(
                        f"Restricción repetida para columna '{raw_name}': UNIQUE"
                    )
                unique = True
                idx += len("UNIQUE")
                continue

            if rest_upper.startswith("PRIMARY KEY", idx):
                if primary_key:
                    raise ValueError(
                        f"Restricción repetida para columna '{raw_name}': PRIMARY KEY"
                    )
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
                    raise ValueError(
                        f"Restricción repetida para columna '{raw_name}': DEFAULT"
                    )

                expr_start = idx + len("DEFAULT")
                while expr_start < length and rest_upper[expr_start] == " ":
                    expr_start += 1

                potential_ends = [length]
                for token in (" NOT NULL", " UNIQUE", " PRIMARY KEY", " DEFAULT"):
                    keyword_pos = rest_upper.find(token, expr_start)
                    if keyword_pos != -1:
                        potential_ends.append(keyword_pos)

                expr_end = min(potential_ends)
                default_expr = rest_original[expr_start:expr_end].strip()
                if not default_expr:
                    raise ValueError(
                        f"Expresión DEFAULT inválida para columna '{raw_name}'"
                    )
                idx = expr_end
                continue

            raise ValueError(
                f"Restricción no permitida para columna '{raw_name}': {raw_type}"
            )

        if autoincrement and base != "INTEGER":
            raise ValueError(
                f"AUTOINCREMENT solo es válido en columnas INTEGER: {raw_type}"
            )

        if autoincrement and not primary_key:
            raise ValueError(
                f"AUTOINCREMENT requiere PRIMARY KEY en la columna '{raw_name}'"
            )

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
            if not _py_is_safe_default_expr(<str>default_expr):
                raise ValueError(
                    f"Expresión DEFAULT potencialmente insegura para columna '{raw_name}'"
                )
            normalized_parts.append(f"DEFAULT {default_expr}")

        sanitized_columns[normalized_name] = " ".join(normalized_parts)

    return sanitized_columns
