import os
import sys

# Force pure mode before importing modules
os.environ["SQLITEPLUS_DISABLE_CYTHON"] = "1"

# Prefer installed wheel over local sources
cwd = os.getcwd()
if cwd in sys.path:
    sys.path.remove(cwd)

import sqliteplus
from sqliteplus.core import schemas
from sqliteplus.core import _schemas_py_fallback as pyfb

def assert_eq(a, b, label):
    if a != b:
        print(f"[DIFF] {label}: {a!r} != {b!r}")
        return False
    return True

print("HAS_CYTHON_SPEEDUPS:", getattr(schemas, "HAS_CYTHON_SPEEDUPS", None))

ok = True

ident_cases = ["valid_name", "bad name", " spaced", "trail ", "a\"b", "name_123", ""]
for s in ident_cases:
    a = schemas.is_valid_sqlite_identifier(s)
    b = pyfb._py_is_valid_sqlite_identifier(s)
    ok &= assert_eq(a, b, f"is_valid_sqlite_identifier({s!r})")

paren_cases = ["(1+2)", "((x))", "(x", "x)", "x", "((a)+(b))"]
for s in paren_cases:
    a = schemas.CreateTableSchema._has_balanced_parentheses(s)
    b = pyfb._py_has_balanced_parentheses(s)
    ok &= assert_eq(a, b, f"_has_balanced_parentheses({s!r})")

strip_cases = ["((x))", "( x )", "x", "((a)+(b))", "((()))", "()"]
for s in strip_cases:
    a = schemas.CreateTableSchema._strip_enclosing_parentheses(s)
    b = pyfb._py_strip_enclosing_parentheses(s)
    ok &= assert_eq(a, b, f"_strip_enclosing_parentheses({s!r})")

call_cases = ["NOW()", "date('now')", "FOO(bar,baz)", "no_call", "SUM(1, 2, 3)"]
for s in call_cases:
    a = schemas.CreateTableSchema._parse_function_call(s)
    b = pyfb._py_parse_function_call(s)
    ok &= assert_eq(a, b, f"_parse_function_call({s!r})")

def_cases = ["NULL", "CURRENT_DATE", "'text'", "1", "1.23e3", "DROP TABLE x", "RAISE(IGNORE)"]
for s in def_cases:
    a = schemas.CreateTableSchema._is_safe_default_expr(s)
    b = pyfb._py_is_safe_default_expr(s)
    ok &= assert_eq(a, b, f"_is_safe_default_expr({s!r})")

cols_cases = [
    {"id": "INTEGER PRIMARY KEY AUTOINCREMENT", "name": "TEXT NOT NULL"},
    {"count": "INTEGER DEFAULT 0", "flag": "NUMERIC UNIQUE"},
    {"blob": "BLOB", "realv": "REAL DEFAULT 3.14"},
]
for idx, case in enumerate(cols_cases):
    a = schemas.CreateTableSchema(columns=case).normalized_columns()
    b = pyfb._py_normalized_columns(case)
    ok &= assert_eq(a, b, f"normalized_columns(case_{idx})")

print("PURE_MODE_EQUIVALENCE:", "OK" if ok else "MISMATCHES FOUND")
if not ok:
    raise SystemExit(2)
print("DONE")
