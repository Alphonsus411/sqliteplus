# cython: language_level=3
"""Declaraciones compartidas de constantes para Cython."""

cdef public object SQLITE_IDENTIFIER_PATTERN
cdef public tuple SQLITE_IDENTIFIER_DISALLOWED_TOKENS
cdef public object ALLOWED_BASE_TYPES
cdef public object DEFAULT_EXPR_NUMERIC_PATTERN
cdef public object DEFAULT_EXPR_STRING_PATTERN
cdef public object DEFAULT_EXPR_ALLOWED_LITERALS
cdef public object DEFAULT_EXPR_ALLOWED_FUNCTIONS
cdef public object DEFAULT_EXPR_DISALLOWED_TOKENS
cdef public object DEFAULT_EXPR_DISALLOWED_KEYWORDS
cdef public object FUNCTION_CALL_PATTERN
