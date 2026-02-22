# cython: language_level=3
# cython: boundscheck=False
# cython: wraparound=False
# cython: initializedcheck=False
# cython: cdivision=True
"""Implementaciones aceleradas en Cython para validación y parsing de esquemas."""

cimport cython

cdef tuple SQLITE_IDENTIFIER_DISALLOWED_TOKENS = (";", "--", "/*", "*/")

@cython.cfunc
@cython.inline
def _has_disallowed_tokens(text: str) -> cython.bint:
    for token in SQLITE_IDENTIFIER_DISALLOWED_TOKENS:
        if token in text:
            return True
    return False


@cython.cfunc
@cython.inline
def _is_control_or_quote(value: str) -> cython.bint:
    cdef int code_point = ord(value)
    return code_point < 32 or value == '"'


@cython.cfunc
def _has_balanced_parentheses_impl(expr: str) -> cython.bint:
    cdef Py_ssize_t depth = 0
    cdef Py_ssize_t idx = 0
    cdef Py_ssize_t length = len(expr)
    cdef str current

    for idx in range(length):
        current = expr[idx]
        if current == "(":
            depth += 1
        elif current == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _strip_enclosing_parentheses_impl(expr: str) -> str:
    cdef str sanitized = expr
    cdef str inner

    while sanitized.startswith("(") and sanitized.endswith(")") and _has_balanced_parentheses_impl(sanitized):
        inner = sanitized[1: len(sanitized) - 1].strip()
        if not inner:
            break
        sanitized = inner
    return sanitized


def _parse_function_call_impl(expr: str):
    cdef Py_ssize_t length = len(expr)
    if length == 0:
        return None

    cdef Py_ssize_t idx = 0
    cdef str char
    cdef Py_ssize_t start = -1
    cdef Py_ssize_t end = -1

    if not (expr[0].isalpha() or expr[0] == "_"):
        return None

    for idx in range(length):
        char = expr[idx]
        if char.isalnum() or char == "_":
            if start == -1:
                start = idx
            continue
        if char == "(":
            end = idx
            break
        return None

    if start == -1 or end == -1:
        return None

    func_name = expr[start:end]
    depth = 0
    cdef Py_ssize_t pos
    for pos in range(end, length):
        char = expr[pos]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                if pos != length - 1:
                    return None
                args = expr[end + 1 : pos].strip()
                return func_name, args
            if depth < 0:
                return None
    return None


cpdef bint is_valid_sqlite_identifier(str identifier):
    if not isinstance(identifier, str):
        return False

    if _has_disallowed_tokens(identifier):
        return False

    cdef Py_ssize_t length = len(identifier)
    if length == 0:
        return False
    if identifier[0].isspace() or identifier[length - 1].isspace():
        return False

    cdef Py_ssize_t idx
    cdef str char
    for idx in range(length):
        char = identifier[idx]
        if _is_control_or_quote(char):
            return False
    return True


cpdef bint has_balanced_parentheses(str expr):
    """Comprueba de forma optimizada que paréntesis estén balanceados."""
    return _has_balanced_parentheses_impl(expr)


cpdef str strip_enclosing_parentheses(str expr):
    """Elimina paréntesis exteriores balanceados para normalizar expresiones."""
    return _strip_enclosing_parentheses_impl(expr)


cpdef parse_function_call(str expr):
    """Parsea llamadas a función simples, devolviendo (nombre, argumentos)."""
    return _parse_function_call_impl(expr)
