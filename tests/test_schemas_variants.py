from time import perf_counter

import pytest

from sqliteplus.core import schemas


pytestmark = pytest.mark.filterwarnings("ignore::pytest.PytestWarning")


@pytest.fixture()
def schema_variants(speedup_variants):
    cython_schemas, _, _ = speedup_variants(force_fallback=False)
    fallback_schemas, _, _ = speedup_variants(force_fallback=True)
    return cython_schemas, fallback_schemas


def _collect_schema_results(module):
    schema = module.CreateTableSchema(
        columns={
            "codigo": "text not null unique default 'hola'",
            "cantidad": "integer primary key autoincrement",
            "total": "real default (round(1.5))",
        }
    )

    return {
        "normalized": schema.normalized_columns(),
        "balanced": module.CreateTableSchema._has_balanced_parentheses("((a+b)/c)")
        and module.CreateTableSchema._has_balanced_parentheses("(1+(2*3))"),
        "parser": module.CreateTableSchema._parse_function_call("trim( nombre )"),
        "strip": module.CreateTableSchema._strip_enclosing_parentheses("( (valor) )"),
        "safe": module.CreateTableSchema._is_safe_default_expr("strftime('%s','now')"),
        "identifier": module.is_valid_sqlite_identifier("Tabla_Valida"),
    }


def test_schema_helpers_match_across_env(schema_variants):
    cython_schemas, fallback_schemas = schema_variants

    cython_results = _collect_schema_results(cython_schemas)
    fallback_results = _collect_schema_results(fallback_schemas)

    assert cython_results == fallback_results


@pytest.mark.skipif(
    not schemas.HAS_CYTHON_SPEEDUPS,
    reason="Extensiones Cython no compiladas; solo se dispone del modo Python",
)
def test_schema_speed_regression_guard(speedup_variants):
    cython_schemas, _, _ = speedup_variants(force_fallback=False)
    fallback_schemas, _, _ = speedup_variants(force_fallback=True)

    columns = {
        "codigo": "integer primary key autoincrement",
        "nombre": "text not null",
        "precio": "real default 0.0",
        "activo": "integer default 1",
    }
    expressions = ["((a+b)/c)" * 5, "lower(nombre)", "strftime('%s','now')"]

    def measure(fn, payloads):
        start = perf_counter()
        for _ in range(200):
            for value in payloads:
                fn(value)
        return (perf_counter() - start) / len(payloads)

    baseline_columns = measure(lambda _: fallback_schemas._normalize_columns_impl(columns), [None])
    cython_columns = measure(lambda _: cython_schemas._normalize_columns_impl(columns), [None])

    baseline_parentheses = measure(
        fallback_schemas._has_balanced_parentheses_impl, expressions
    )
    cython_parentheses = measure(cython_schemas._has_balanced_parentheses_impl, expressions)

    # Umbrales tolerantes (30% de holgura) pero útiles para detectar regresiones evidentes.
    assert cython_columns <= baseline_columns * 1.3
    assert cython_parentheses <= baseline_parentheses * 1.3


@pytest.mark.parametrize("force_flag", [True, False])
def test_env_flag_is_respected(monkeypatch, speedup_variants, force_flag):
    if force_flag:
        monkeypatch.setenv("SQLITEPLUS_DISABLE_CYTHON", "1")
    else:
        monkeypatch.delenv("SQLITEPLUS_DISABLE_CYTHON", raising=False)

    module, _, _ = speedup_variants(force_fallback=force_flag)

    schema = module.CreateTableSchema(columns={"id": "integer primary key"})
    assert schema.normalized_columns() == {"id": "INTEGER PRIMARY KEY"}

    if force_flag:
        assert module.DISABLE_CYTHON_SPEEDUPS is True
    else:
        assert module.DISABLE_CYTHON_SPEEDUPS is False
