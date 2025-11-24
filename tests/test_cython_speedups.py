import pytest
from time import perf_counter

from sqliteplus.core import schemas


@pytest.mark.skipif(not schemas.HAS_CYTHON_SPEEDUPS, reason="Extensiones Cython no compiladas")
def test_fast_module_is_loaded():
    assert schemas._schemas_fast is not None
    assert schemas.is_valid_sqlite_identifier("tabla1")


def test_identifier_validation_consistency():
    candidates = [
        "tabla_valida",
        "_otraTabla",
        "tabla con espacios",
        " tabla",
        "tabla\u0007control",
        "tabla;drop",
    ]

    for candidate in candidates:
        assert schemas.is_valid_sqlite_identifier(candidate) == schemas._py_is_valid_sqlite_identifier(candidate)


@pytest.mark.skipif(not schemas.HAS_CYTHON_SPEEDUPS, reason="Extensiones Cython no compiladas")
def test_parentheses_speed_improvement():
    heavy_inputs = [
        "(" * 80 + "x" + ")" * 80,
        "((" * 40 + "valor" + ")" * 80,
        "((a+b)/c)" * 30,
    ]
    iterations = 4000

    def measure(fn):
        start = perf_counter()
        for _ in range(iterations):
            for expr in heavy_inputs:
                fn(expr)
        return perf_counter() - start

    baseline = measure(schemas._py_has_balanced_parentheses)
    optimized = measure(schemas._schemas_fast.has_balanced_parentheses)

    assert optimized <= baseline * 0.8


@pytest.mark.skipif(not schemas.HAS_CYTHON_SPEEDUPS, reason="Extensiones Cython no compiladas")
def test_function_call_parser_matches_python():
    samples = [
        "now()",
        "trim( nombre )",
        "lower(column_name)",
        "invalid call(",
        "sinparentesis",
    ]

    for expr in samples:
        assert schemas._parse_function_call_impl(expr) == schemas._py_parse_function_call(expr)
