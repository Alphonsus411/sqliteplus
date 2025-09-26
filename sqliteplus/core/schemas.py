from pydantic import BaseModel, root_validator, validator
from typing import Any, ClassVar, Dict
import re

class CreateTableSchema(BaseModel):
    """Esquema recibido al crear una tabla."""

    columns: Dict[str, str]

    _column_name_pattern: ClassVar[re.Pattern[str]] = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
    _allowed_base_types: ClassVar[set[str]] = {"INTEGER", "TEXT", "REAL", "BLOB", "NUMERIC"}
    _allowed_suffixes: ClassVar[set[str]] = {"", "NOT NULL", "UNIQUE", "PRIMARY KEY"}
    _allowed_integer_suffixes: ClassVar[set[str]] = _allowed_suffixes | {"PRIMARY KEY AUTOINCREMENT"}

    def normalized_columns(self) -> Dict[str, str]:
        """Valida y normaliza los nombres y tipos de columna permitidos."""

        if not self.columns:
            raise ValueError("Se requiere al menos una columna para crear la tabla")

        sanitized_columns: Dict[str, str] = {}
        for raw_name, raw_type in self.columns.items():
            if not self._column_name_pattern.match(raw_name):
                raise ValueError(f"Nombre de columna inválido: {raw_name}")

            normalized_type = " ".join(raw_type.strip().upper().split())
            if not normalized_type:
                raise ValueError(f"Tipo de columna vacío para '{raw_name}'")

            base, *rest = normalized_type.split(" ")
            if base not in self._allowed_base_types:
                raise ValueError(f"Tipo de dato no permitido para '{raw_name}': {raw_type}")

            suffix = " ".join(rest)
            if base == "INTEGER":
                if suffix not in self._allowed_integer_suffixes:
                    raise ValueError(
                        f"Restricción no permitida para columna '{raw_name}': {raw_type}"
                    )
            else:
                if suffix not in self._allowed_suffixes:
                    raise ValueError(
                        f"Restricción no permitida para columna '{raw_name}': {raw_type}"
                    )

            normalized_definition = " ".join(filter(None, [base, suffix]))
            sanitized_columns[raw_name] = normalized_definition

        return sanitized_columns

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
    def validate_values(cls, values: Dict[str, Any]) -> Dict[str, Any]:
        if not values:
            raise ValueError("Se requiere al menos un par columna/valor para insertar datos")

        sanitized_values: Dict[str, Any] = {}
        for column, value in values.items():
            if not isinstance(column, str):
                raise TypeError("Los nombres de columna deben ser cadenas de texto")

            if not column.strip():
                raise ValueError("Los nombres de columna no pueden estar vacíos")

            sanitized_values[column] = value

        return sanitized_values
