"""Pruebas que comparan validadores de esquemas entre la ruta Cython y la de fallback."""

import os
from time import perf_counter

import pytest

MIN_EXPECTED_IMPROVEMENT = float(os.getenv("SQLITEPLUS_MIN_SPEEDUP", "0.2"))


@pytest.fixture()
def schema_validator_variants(speedup_variants):
    cython_schemas, _, _ = speedup_variants(force_fallback=False)
    fallback_schemas, _, _ = speedup_variants(force_fallback=True)
    return cython_schemas, fallback_schemas


def _collect_validator_results(module):
    schema_cls = module.CreateTableSchema

    identifiers = [
        "tabla_ok",
        "_prefijo",
        "contiene espacio",
        "otra;tabla",
        "MiTabla",
    ]
    default_exprs = [
        "(1 + 2) * 3",
        "(strftime('%s','now'))",
        "random()",
        "'texto'",
        "lower(nombre)",
    ]

    return {
        "identifier_checks": [module.is_valid_sqlite_identifier(name) for name in identifiers],
        "safe_defaults": [schema_cls._is_safe_default_expr(expr) for expr in default_exprs],
        "parser": [schema_cls._parse_function_call(expr) for expr in default_exprs],
        "stripped": [schema_cls._strip_enclosing_parentheses(expr) for expr in default_exprs],
        "balanced": [schema_cls._has_balanced_parentheses(expr) for expr in default_exprs],
    }


def test_schema_validators_produce_same_results(schema_validator_variants):
    cython_schemas, fallback_schemas = schema_validator_variants

    cython_results = _collect_validator_results(cython_schemas)
    fallback_results = _collect_validator_results(fallback_schemas)

    assert cython_results == fallback_results


@pytest.mark.benchmark(min_rounds=3)
def test_schema_validator_speedups(benchmark, speedup_variants):
    cython_schemas, _, _ = speedup_variants(force_fallback=False)
    if not cython_schemas.HAS_CYTHON_SPEEDUPS:
        pytest.skip("Extensiones Cython no están disponibles")

    fallback_schemas, _, _ = speedup_variants(force_fallback=True)

    identifiers = ["tabla_ok", "otra_tabla", "_prefijo", "con espacio", "otra;tabla"] * 40
    default_exprs = [
        "(1 + 2) * 3",
        "strftime('%s','now')",
        "random()",
        "'texto'",
        "lower(nombre)",
        "((a+b)/c)",
        "((a+(b*c))/d)",
    ] * 25

    def run_both_paths():
        start = perf_counter()
        for name in identifiers:
            fallback_schemas.is_valid_sqlite_identifier(name)
        for expr in default_exprs:
            fallback_schemas.CreateTableSchema._is_safe_default_expr(expr)
        fallback_time = perf_counter() - start

        start = perf_counter()
        for name in identifiers:
            cython_schemas.is_valid_sqlite_identifier(name)
        for expr in default_exprs:
            cython_schemas.CreateTableSchema._is_safe_default_expr(expr)
        cython_time = perf_counter() - start

        return fallback_time, cython_time

    fallback_time, cython_time = benchmark(run_both_paths)

    assert cython_time <= fallback_time * (1 - MIN_EXPECTED_IMPROVEMENT)
