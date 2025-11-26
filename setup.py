from __future__ import annotations

import os
from pathlib import Path

from Cython.Build import cythonize
from setuptools import Extension, setup


def discover_extensions() -> list[Extension]:
    if os.environ.get("SQLITEPLUS_DISABLE_CYTHON"):
        return []

    pyx_files = sorted(Path("sqliteplus").rglob("*.pyx"))
    include_dirs = ["sqliteplus"]

    extensions: list[Extension] = []
    for pyx_path in pyx_files:
        module_name = ".".join(pyx_path.with_suffix("").parts)
        extensions.append(Extension(module_name, [str(pyx_path)], include_dirs=include_dirs))

    return extensions


setup(
    ext_modules=cythonize(
        discover_extensions(),
        language_level="3",
        annotate=False,
        compiler_directives={
            "boundscheck": False,
            "wraparound": False,
            "initializedcheck": False,
            "cdivision": True,
        },
    ),
)
