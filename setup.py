from Cython.Build import cythonize
from setuptools import Extension, setup

extensions = [
    Extension(
        name="sqliteplus.core._schemas_fast",
        sources=["sqliteplus/core/_schemas_fast.pyx"],
    ),
]

setup(
    ext_modules=cythonize(
        extensions,
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
