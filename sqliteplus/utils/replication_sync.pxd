# cython: language_level=3
cimport cython
from cpython.size_t cimport Py_ssize_t

cdef class SQLiteReplication:
    cdef public str db_path
    cdef public object backup_dir
    cdef public object cipher_key

    cpdef object export_to_csv(self, str table_name, str output_file, bint overwrite=*)
    cpdef object backup_database(self)
    cpdef object replicate_database(self, str target_db_path)
    cpdef object _get_timestamp(self)
    cpdef cython.bint _is_valid_table_name(self, object table_name)
    cpdef str _escape_identifier(str identifier)
    cpdef list _copy_wal_and_shm(self, object source_path, object target_path)
    cpdef object _default_local_db(self)
    cpdef object _select_writable_path(self, object candidate)
    cpdef object _copy_database_to_local(self, object source, object destination)
    cpdef cython.bint _is_inside_package(self, object path)
    cpdef cython.bint _can_write_to(self, object directory)
    cpdef object _ensure_local_database(self, object target)
