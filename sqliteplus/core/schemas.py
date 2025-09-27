from pydantic import BaseModel, root_validator, validator
from typing import Any, ClassVar, Dict
import re

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

    _column_name_pattern: ClassVar[re.Pattern[str]] = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
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
        for raw_name, raw_type in self.columns.items():
            if not self._column_name_pattern.match(raw_name):
                raise ValueError(f"Nombre de columna inválido: {raw_name}")

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

            sanitized_columns[raw_name] = " ".join(normalized_parts)

        return sanitized_columns

    @classmethod
    def _is_safe_default_expr(cls, expr: str) -> bool:
        sanitized = expr.strip()
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

        function_match = re.fullmatch(r"([A-Za-z_][A-Za-z0-9_]*)(?:\s*\(\s*\))?", sanitized)
        if function_match:
            if function_match.group(1).upper() in cls._default_expr_allowed_functions:
                return True

        return False

class InsertDataSchema(BaseModel):
    """Esquema utilizado para insertar datos en una tabla existente."""

    values: Dict[str, Any]

    @root_validator(pre=True)
    def ensure_values_key(cls, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Permite aceptar payloads planos y normalizarlos bajo la clave 'values'."""

        if isinstance(payload, dict) and "values" not in payload:
            return {"values": payload}
        return payload

    @validator("values")
    def validate_values(cls, v: Dict[str, Any]) -> Dict[str, Any]:
        if not v:
            raise ValueError("Se requiere al menos un par columna/valor para insertar datos")

        sanitized_values: Dict[str, Any] = {}
        for column, value in v.items():
            if not isinstance(column, str):
                raise TypeError("Los nombres de columna deben ser cadenas de texto")

            if not column.strip():
                raise ValueError("Los nombres de columna no pueden estar vacíos")

            sanitized_values[column] = value

        return sanitized_values
