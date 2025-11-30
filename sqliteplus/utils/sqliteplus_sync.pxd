# cython: language_level=3
from cpython.size_t cimport Py_ssize_t

cdef public tuple SQLITEPLUS_PUBLIC_API

cdef class SQLitePlusCipherError(RuntimeError):
    pass

cdef class SQLitePlusQueryError(RuntimeError):
    pass

cdef class SQLitePlus:
    cdef public str db_path
    cdef public object cipher_key
    cdef object lock

    cpdef object get_connection(self)
    cpdef object execute_query(self, object query, object params=*)
    cpdef object fetch_query(self, object query, object params=*)
    cpdef object fetch_query_with_columns(self, object query, object params=*)
    cpdef object log_action(self, object action)
    cpdef object list_tables(self, bint include_views=*, bint include_row_counts=*)
    cpdef object describe_table(self, str table_name)
    cpdef object get_database_statistics(self, bint include_views=*)
    cpdef str _escape_identifier(self, str table_name)

cpdef void apply_cipher_key(object connection, object cipher_key)
