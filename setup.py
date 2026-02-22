from __future__ import annotations

import json
import os
from pathlib import Path

from setuptools import Extension, setup

def strtobool_env(name: str, *, default: bool = False) -> bool:
    value = os.environ.get(name)
    if value is None:
        return default
    return value.lower() not in {"", "0", "false", "off", "no"}


def collect_include_dirs() -> list[str]:
    include_dirs: set[str] = {"sqliteplus"}
    for suffix in (".pxd", ".pxi"):
        for path in Path("sqliteplus").rglob(f"*{suffix}"):
            include_dirs.add(str(path.parent))
    return sorted(include_dirs)


def collect_define_macros() -> list[tuple[str, str]]:
    macros: list[tuple[str, str]] = []
    if strtobool_env("SQLITEPLUS_CYTHON_TRACE"):
        macros.extend([("CYTHON_TRACE", "1"), ("CYTHON_TRACE_NOGIL", "1")])
    return macros


def load_profiled_targets() -> set[str] | None:
    if strtobool_env("SQLITEPLUS_IGNORE_CYTHON_TARGETS"):
        return None

    targets_path = os.environ.get(
        "SQLITEPLUS_CYTHON_TARGETS",
        str(Path("reports") / "cython_candidates.json"),
    )
    path = Path(targets_path)
    if not path.exists():
        return None

    try:
        payload = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    modules = payload.get("modules")
    if not isinstance(modules, list):
        return None

    return {str(module) for module in modules}


def discover_extensions() -> list[Extension]:
    if strtobool_env("SQLITEPLUS_DISABLE_CYTHON"):
        return []

    pyx_files = sorted(Path("sqliteplus").rglob("*.pyx"))
    profiled_targets = None if strtobool_env("SQLITEPLUS_FORCE_CYTHON") else load_profiled_targets()
    include_dirs = collect_include_dirs()
    define_macros = collect_define_macros()

    extensions: list[Extension] = []
    for pyx_path in pyx_files:
        module_name = ".".join(pyx_path.with_suffix("").parts)
        if profiled_targets is not None and module_name not in profiled_targets:
            continue
        extensions.append(
            Extension(
                module_name,
                [str(pyx_path)],
                include_dirs=include_dirs,
                define_macros=define_macros,
            )
        )

    return extensions


extensions = discover_extensions()
ext_modules = []
if extensions:
    try:
        from Cython.Build import cythonize
    except Exception:
        # Sin Cython disponible: omite la compilación y continúa en modo puro Python
        ext_modules = []
    else:
        ext_modules = cythonize(
            extensions,
            language_level="3",
            annotate=strtobool_env("SQLITEPLUS_CYTHON_ANNOTATE"),
            compiler_directives={
                "boundscheck": False,
                "wraparound": False,
                "initializedcheck": False,
                "cdivision": True,
            },
        )


setup(ext_modules=ext_modules)
