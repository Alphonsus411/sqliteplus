from __future__ import annotations

import os
from pathlib import Path

from Cython.Build import cythonize
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


def discover_extensions() -> list[Extension]:
    if strtobool_env("SQLITEPLUS_DISABLE_CYTHON"):
        return []

    pyx_files = sorted(Path("sqliteplus").rglob("*.pyx"))
    include_dirs = collect_include_dirs()
    define_macros = collect_define_macros()

    extensions: list[Extension] = []
    for pyx_path in pyx_files:
        module_name = ".".join(pyx_path.with_suffix("").parts)
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
