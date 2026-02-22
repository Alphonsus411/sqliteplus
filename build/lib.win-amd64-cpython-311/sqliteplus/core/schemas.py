import os
import re
from typing import Any, ClassVar, Dict

from pydantic import BaseModel, field_validator, model_validator

from sqliteplus.core._schemas_constants import (
    ALLOWED_BASE_TYPES,
    DEFAULT_EXPR_ALLOWED_FUNCTIONS,
    DEFAULT_EXPR_ALLOWED_LITERALS,
    DEFAULT_EXPR_DISALLOWED_KEYWORDS,
    DEFAULT_EXPR_DISALLOWED_TOKENS,
    DEFAULT_EXPR_NUMERIC_PATTERN,
    DEFAULT_EXPR_STRING_PATTERN,
    SQLITE_IDENTIFIER_DISALLOWED_TOKENS,
    SQLITE_IDENTIFIER_PATTERN,
)


SQLITEPLUS_DISABLE_CYTHON = os.getenv("SQLITEPLUS_DISABLE_CYTHON", "").lower() in {
    "1",
    "true",
    "yes",
}
DISABLE_CYTHON_SPEEDUPS = SQLITEPLUS_DISABLE_CYTHON


if not SQLITEPLUS_DISABLE_CYTHON:
    try:  # pragma: no cover - la ruta acelerada se valida aparte
        from sqliteplus.core import schemas_cy as _schemas_api
    except ImportError:  # pragma: no cover - ausencia comprobada en pruebas
        _schemas_api = None
else:  # pragma: no cover - se fuerza la ruta lenta
    _schemas_api = None

if _schemas_api is not None:
    _py_is_valid_sqlite_identifier = _schemas_api._py_is_valid_sqlite_identifier
    _py_has_balanced_parentheses = _schemas_api._py_has_balanced_parentheses
    _py_strip_enclosing_parentheses = _schemas_api._py_strip_enclosing_parentheses
    _py_parse_function_call = _schemas_api._py_parse_function_call
    _py_is_safe_default_expr = _schemas_api._py_is_safe_default_expr
    _py_normalized_columns = _schemas_api._py_normalized_columns
else:
    from sqliteplus.core import _schemas_py_fallback as _schemas_py

    _py_is_valid_sqlite_identifier = _schemas_py._py_is_valid_sqlite_identifier
    _py_has_balanced_parentheses = _schemas_py._py_has_balanced_parentheses
    _py_strip_enclosing_parentheses = _schemas_py._py_strip_enclosing_parentheses
    _py_parse_function_call = _schemas_py._py_parse_function_call
    _py_is_safe_default_expr = _schemas_py._py_is_safe_default_expr
    _py_normalized_columns = _schemas_py._py_normalized_columns


if not DISABLE_CYTHON_SPEEDUPS:
    try:  # pragma: no cover - la rama rápida se valida aparte
        from sqliteplus.core import _schemas_fast
    except ImportError:  # pragma: no cover - la ausencia también se comprueba
        _schemas_fast = None

    try:  # pragma: no cover - la rama rápida se valida aparte
        from sqliteplus.core import _schemas_columns
    except ImportError:  # pragma: no cover - la ausencia también se comprueba
        _schemas_columns = None
else:  # pragma: no cover - se valida forzando la ruta lenta en pruebas
    _schemas_fast = None
    _schemas_columns = None

HAS_CYTHON_SPEEDUPS = all(
    module is not None for module in (_schemas_fast, _schemas_columns, _schemas_api)
)

if _schemas_fast is not None:
    is_valid_sqlite_identifier = _schemas_fast.is_valid_sqlite_identifier
    _has_balanced_parentheses_impl = _schemas_fast.has_balanced_parentheses
    _strip_enclosing_parentheses_impl = _schemas_fast.strip_enclosing_parentheses
    _parse_function_call_impl = _schemas_fast.parse_function_call
else:
    is_valid_sqlite_identifier = _py_is_valid_sqlite_identifier
    _has_balanced_parentheses_impl = _py_has_balanced_parentheses
    _strip_enclosing_parentheses_impl = _py_strip_enclosing_parentheses
    _parse_function_call_impl = _py_parse_function_call

if _schemas_columns is not None:
    _normalize_columns_impl = _schemas_columns.normalized_columns
    _is_safe_default_expr_impl = _schemas_columns.is_safe_default_expr
else:
    _normalize_columns_impl = _py_normalized_columns
    _is_safe_default_expr_impl = _py_is_safe_default_expr


class CreateTableSchema(BaseModel):
    """Esquema recibido al crear una tabla.

    Se permiten columnas basadas en los tipos primitivos de SQLite y las
    siguientes combinaciones de restricciones, que son validadas de manera
    independiente y luego normalizadas:

    * ``PRIMARY KEY`` (con ``AUTOINCREMENT`` únicamente para ``INTEGER``).
    * ``NOT NULL`` y ``UNIQUE`` de forma individual o combinadas.
    * ``DEFAULT <expresión>`` junto con cualquiera de las restricciones
      anteriores.

    Durante la normalización las restricciones se ordenan como ``PRIMARY KEY``
    (``AUTOINCREMENT`` si procede), ``NOT NULL``, ``UNIQUE`` y finalmente
    ``DEFAULT``.
    """

    columns: Dict[str, str]

    _column_name_pattern: ClassVar[re.Pattern[str]] = SQLITE_IDENTIFIER_PATTERN
    _allowed_base_types: ClassVar[set[str]] = ALLOWED_BASE_TYPES
    _default_expr_numeric_pattern: ClassVar[re.Pattern[str]] = DEFAULT_EXPR_NUMERIC_PATTERN
    _default_expr_string_pattern: ClassVar[re.Pattern[str]] = DEFAULT_EXPR_STRING_PATTERN
    _default_expr_allowed_literals: ClassVar[set[str]] = DEFAULT_EXPR_ALLOWED_LITERALS
    _default_expr_allowed_functions: ClassVar[set[str]] = DEFAULT_EXPR_ALLOWED_FUNCTIONS
    _default_expr_disallowed_tokens: ClassVar[tuple[str, ...]] = DEFAULT_EXPR_DISALLOWED_TOKENS
    _default_expr_disallowed_keywords: ClassVar[tuple[str, ...]] = DEFAULT_EXPR_DISALLOWED_KEYWORDS

    def normalized_columns(self) -> Dict[str, str]:
        """Valida y normaliza los nombres y tipos de columna permitidos."""
        return _normalize_columns_impl(self.columns)

    @classmethod
    def _is_safe_default_expr(cls, expr: str) -> bool:
        return bool(_is_safe_default_expr_impl(expr))

    @staticmethod
    def _has_balanced_parentheses(expr: str) -> bool:
        return bool(_has_balanced_parentheses_impl(expr))

    @classmethod
    def _strip_enclosing_parentheses(cls, expr: str) -> str:
        return _strip_enclosing_parentheses_impl(expr)

    @staticmethod
    def _parse_function_call(expr: str) -> tuple[str, str] | None:
        return _parse_function_call_impl(expr)


class InsertDataSchema(BaseModel):
    """Esquema utilizado para insertar datos en una tabla existente."""

    values: Dict[str, Any]

    @model_validator(mode="before")
    @classmethod
    def ensure_values_key(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Permite aceptar payloads planos y normalizarlos bajo la clave 'values'."""

        if isinstance(payload, dict) and "values" not in payload:
            return {"values": payload}
        return payload

    @field_validator("values")
    @classmethod
    def validate_values(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if not values:
            raise ValueError("Se requiere al menos un par columna/valor para insertar datos")

        sanitized_values: Dict[str, Any] = {}
        for column, value in values.items():
            if not isinstance(column, str):
                raise TypeError("Los nombres de columna deben ser cadenas de texto")

            normalized_column = column.strip()
            if not normalized_column:
                raise ValueError("Los nombres de columna no pueden estar vacíos")

            if not is_valid_sqlite_identifier(normalized_column):
                raise ValueError(f"Nombre de columna inválido: {column}")

            sanitized_values[normalized_column] = value

        return sanitized_values
