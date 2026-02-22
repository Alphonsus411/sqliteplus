"""Constantes y patrones compartidos para validación de esquemas."""

from __future__ import annotations

import re

SQLITE_IDENTIFIER_PATTERN = re.compile(r'^(?!\s)(?!.*\s$)[^"\x00-\x1F]+$')
SQLITE_IDENTIFIER_DISALLOWED_TOKENS: tuple[str, ...] = (";", "--", "/*", "*/")
ALLOWED_BASE_TYPES: set[str] = {"INTEGER", "TEXT", "REAL", "BLOB", "NUMERIC"}
DEFAULT_EXPR_NUMERIC_PATTERN = re.compile(r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$")
DEFAULT_EXPR_STRING_PATTERN = re.compile(r"^'(?:''|[^'])*'$")
DEFAULT_EXPR_ALLOWED_LITERALS: set[str] = {"NULL", "TRUE", "FALSE"}
DEFAULT_EXPR_ALLOWED_FUNCTIONS: set[str] = {
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
DEFAULT_EXPR_DISALLOWED_TOKENS: tuple[str, ...] = (";", "--", "/*", "*/", " PRAGMA ")
DEFAULT_EXPR_DISALLOWED_KEYWORDS: tuple[str, ...] = (
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
FUNCTION_CALL_PATTERN = re.compile(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(")

__all__ = [
    "SQLITE_IDENTIFIER_PATTERN",
    "SQLITE_IDENTIFIER_DISALLOWED_TOKENS",
    "ALLOWED_BASE_TYPES",
    "DEFAULT_EXPR_NUMERIC_PATTERN",
    "DEFAULT_EXPR_STRING_PATTERN",
    "DEFAULT_EXPR_ALLOWED_LITERALS",
    "DEFAULT_EXPR_ALLOWED_FUNCTIONS",
    "DEFAULT_EXPR_DISALLOWED_TOKENS",
    "DEFAULT_EXPR_DISALLOWED_KEYWORDS",
    "FUNCTION_CALL_PATTERN",
]
