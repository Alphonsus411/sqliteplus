# cython: language_level=3

cdef tuple SQLITE_IDENTIFIER_DISALLOWED_TOKENS

cpdef bint is_valid_sqlite_identifier(str identifier)
cpdef bint has_balanced_parentheses(str expr)
cpdef str strip_enclosing_parentheses(str expr)
cpdef parse_function_call(str expr)
