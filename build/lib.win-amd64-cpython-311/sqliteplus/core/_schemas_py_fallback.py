"""Implementaciones puramente en Python para los helpers de ``schemas``."""

from __future__ import annotations

from typing import Dict

from sqliteplus.core._schemas_constants import (
    ALLOWED_BASE_TYPES,
    DEFAULT_EXPR_ALLOWED_FUNCTIONS,
    DEFAULT_EXPR_ALLOWED_LITERALS,
    DEFAULT_EXPR_DISALLOWED_KEYWORDS,
    DEFAULT_EXPR_DISALLOWED_TOKENS,
    DEFAULT_EXPR_NUMERIC_PATTERN,
    DEFAULT_EXPR_STRING_PATTERN,
    FUNCTION_CALL_PATTERN,
    SQLITE_IDENTIFIER_DISALLOWED_TOKENS,
    SQLITE_IDENTIFIER_PATTERN,
)


def _py_is_valid_sqlite_identifier(identifier: str) -> bool:
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
    match = FUNCTION_CALL_PATTERN.match(expr)
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


def _py_is_safe_default_expr(expr: str) -> bool:
    sanitized = _py_strip_enclosing_parentheses(expr.strip())
    upper = f" {sanitized.upper()} "

    for token in DEFAULT_EXPR_DISALLOWED_TOKENS:
        if token in sanitized:
            return False

    for keyword in DEFAULT_EXPR_DISALLOWED_KEYWORDS:
        if keyword in upper:
            return False

    if DEFAULT_EXPR_NUMERIC_PATTERN.match(sanitized):
        return True

    if sanitized.upper() in DEFAULT_EXPR_ALLOWED_LITERALS:
        return True

    if DEFAULT_EXPR_STRING_PATTERN.match(sanitized):
        return True

    function_call = _py_parse_function_call(sanitized)
    if function_call:
        func_name, _ = function_call
        if func_name.upper() in DEFAULT_EXPR_ALLOWED_FUNCTIONS:
            return True

    return False


def _py_normalized_columns(columns: Dict[str, str]) -> Dict[str, str]:
    if not columns:
        raise ValueError("Se requiere al menos una columna para crear la tabla")

    sanitized_columns: Dict[str, str] = {}
    seen_names: set[str] = set()
    for raw_name, raw_type in columns.items():
        normalized_name = raw_name.strip()
        if not normalized_name:
            raise ValueError("Los nombres de columna no pueden estar vacíos")

        if not SQLITE_IDENTIFIER_PATTERN.match(normalized_name):
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
        if base not in ALLOWED_BASE_TYPES:
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
            if not _py_is_safe_default_expr(default_expr):
                raise ValueError(
                    f"Expresión DEFAULT potencialmente insegura para columna '{raw_name}'"
                )
            normalized_parts.append(f"DEFAULT {default_expr}")

        sanitized_columns[normalized_name] = " ".join(normalized_parts)

    return sanitized_columns
