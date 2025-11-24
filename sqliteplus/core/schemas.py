import re
from typing import Any, ClassVar, Dict

from pydantic import BaseModel, field_validator, model_validator


SQLITE_IDENTIFIER_PATTERN = re.compile(r'^(?!\s)(?!.*\s$)[^"\x00-\x1F]+$')
SQLITE_IDENTIFIER_DISALLOWED_TOKENS: tuple[str, ...] = (";", "--", "/*", "*/")


def _py_is_valid_sqlite_identifier(identifier: str) -> bool:
    """Implementación original en Python para validar identificadores."""

    if not isinstance(identifier, str):
        return False

    if any(token in identifier for token in SQLITE_IDENTIFIER_DISALLOWED_TOKENS):
        return False

    return bool(SQLITE_IDENTIFIER_PATTERN.match(identifier))


def _py_has_balanced_parentheses(expr: str) -> bool:
    depth = 0
    for char in expr:
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth < 0:
                return False
    return depth == 0


def _py_strip_enclosing_parentheses(expr: str) -> str:
    sanitized = expr
    while (
        sanitized.startswith("(")
        and sanitized.endswith(")")
        and _py_has_balanced_parentheses(sanitized)
    ):
        inner = sanitized[1:-1].strip()
        if not inner:
            break
        sanitized = inner
    return sanitized


def _py_parse_function_call(expr: str) -> tuple[str, str] | None:
    match = re.match(r"([A-Za-z_][A-Za-z0-9_]*)\s*\(", expr)
    if not match:
        return None

    func_name = match.group(1)
    idx = match.end() - 1  # position of the opening parenthesis
    depth = 0
    for pos in range(idx, len(expr)):
        char = expr[pos]
        if char == "(":
            depth += 1
        elif char == ")":
            depth -= 1
            if depth == 0:
                if pos != len(expr) - 1:
                    return None
                args = expr[idx + 1 : pos].strip()
                return func_name, args
            if depth < 0:
                return None
    return None


try:  # pragma: no cover - la rama rápida se valida aparte
    from sqliteplus.core import _schemas_fast
except ImportError:  # pragma: no cover - la ausencia también se comprueba
    _schemas_fast = None

HAS_CYTHON_SPEEDUPS = _schemas_fast is not None

if HAS_CYTHON_SPEEDUPS:
    is_valid_sqlite_identifier = _schemas_fast.is_valid_sqlite_identifier
    _has_balanced_parentheses_impl = _schemas_fast.has_balanced_parentheses
    _strip_enclosing_parentheses_impl = _schemas_fast.strip_enclosing_parentheses
    _parse_function_call_impl = _schemas_fast.parse_function_call
else:
    is_valid_sqlite_identifier = _py_is_valid_sqlite_identifier
    _has_balanced_parentheses_impl = _py_has_balanced_parentheses
    _strip_enclosing_parentheses_impl = _py_strip_enclosing_parentheses
    _parse_function_call_impl = _py_parse_function_call


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
    _allowed_base_types: ClassVar[set[str]] = {"INTEGER", "TEXT", "REAL", "BLOB", "NUMERIC"}
    _default_expr_numeric_pattern: ClassVar[re.Pattern[str]] = re.compile(
        r"^[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][+-]?\d+)?$"
    )
    _default_expr_string_pattern: ClassVar[re.Pattern[str]] = re.compile(r"^'(?:''|[^'])*'$")
    _default_expr_allowed_literals: ClassVar[set[str]] = {"NULL", "TRUE", "FALSE"}
    _default_expr_allowed_functions: ClassVar[set[str]] = {
        "CURRENT_TIMESTAMP",
        "CURRENT_DATE",
        "CURRENT_TIME",
        "DATE",
        "TIME",
        "DATETIME",
    }
    _default_expr_disallowed_tokens: ClassVar[tuple[str, ...]] = (";", "--", "/*", "*/")
    _default_expr_disallowed_keywords: ClassVar[tuple[str, ...]] = (
        " ATTACH ",
        " DETACH ",
        " SELECT ",
        " INSERT ",
        " UPDATE ",
        " DELETE ",
        " DROP ",
        " ALTER ",
        " CREATE ",
        " PRAGMA ",
    )

    def normalized_columns(self) -> Dict[str, str]:
        """Valida y normaliza los nombres y tipos de columna permitidos."""

        if not self.columns:
            raise ValueError("Se requiere al menos una columna para crear la tabla")

        sanitized_columns: Dict[str, str] = {}
        seen_names: set[str] = set()
        for raw_name, raw_type in self.columns.items():
            normalized_name = raw_name.strip()
            if not normalized_name:
                raise ValueError("Los nombres de columna no pueden estar vacíos")

            if not self._column_name_pattern.match(normalized_name):
                raise ValueError(f"Nombre de columna inválido: {raw_name}")

            if any(token in normalized_name for token in SQLITE_IDENTIFIER_DISALLOWED_TOKENS):
                raise ValueError(f"Nombre de columna inválido: {raw_name}")

            normalized_key = normalized_name.casefold()
            if normalized_key in seen_names:
                raise ValueError(
                    f"Nombre de columna duplicado tras normalización: {normalized_name}"
                )
            seen_names.add(normalized_key)

            normalized_original = " ".join(raw_type.strip().split())
            if not normalized_original:
                raise ValueError(f"Tipo de columna vacío para '{raw_name}'")

            base_original, *rest_original_tokens = normalized_original.split(" ")
            base = base_original.upper()
            if base not in self._allowed_base_types:
                raise ValueError(f"Tipo de dato no permitido para '{raw_name}': {raw_type}")

            rest_original = " ".join(rest_original_tokens)
            rest_upper = rest_original.upper()

            not_null = False
            unique = False
            primary_key = False
            autoincrement = False
            default_expr: str | None = None

            idx = 0
            length = len(rest_upper)
            while idx < length:
                if idx < length and rest_upper[idx] == " ":
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
                    for keyword in (" NOT NULL", " UNIQUE", " PRIMARY KEY", " DEFAULT"):
                        keyword_pos = rest_upper.find(keyword, expr_start)
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
                if not self._is_safe_default_expr(default_expr):
                    raise ValueError(
                        f"Expresión DEFAULT potencialmente insegura para columna '{raw_name}'"
                    )
                normalized_parts.append(f"DEFAULT {default_expr}")

            sanitized_columns[normalized_name] = " ".join(normalized_parts)

        return sanitized_columns

    @classmethod
    def _is_safe_default_expr(cls, expr: str) -> bool:
        sanitized = cls._strip_enclosing_parentheses(expr.strip())
        upper = f" {sanitized.upper()} "

        for token in cls._default_expr_disallowed_tokens:
            if token in sanitized:
                return False

        for keyword in cls._default_expr_disallowed_keywords:
            if keyword in upper:
                return False

        if cls._default_expr_numeric_pattern.match(sanitized):
            return True

        if sanitized.upper() in cls._default_expr_allowed_literals:
            return True

        if cls._default_expr_string_pattern.match(sanitized):
            return True

        function_call = cls._parse_function_call(sanitized)
        if function_call:
            func_name, _ = function_call
            if func_name.upper() in cls._default_expr_allowed_functions:
                return True

        return False

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
