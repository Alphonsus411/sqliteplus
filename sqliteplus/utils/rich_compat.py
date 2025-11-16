"""Compatibilidad con Rich con un respaldo sencillo basado en texto.

Este módulo intenta importar las clases principales de Rich utilizadas por
``sqliteplus.cli``. Si Rich no está instalado, provee implementaciones muy
simples que producen texto sin formato aprovechable en los tests y para el
usuario final en entornos mínimos (por ejemplo en la imagen de CI).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Sequence

try:  # pragma: no cover - se ejecuta en entornos con Rich instalado
    from rich import box  # type: ignore
    from rich.console import Console  # type: ignore
    from rich.panel import Panel  # type: ignore
    from rich.syntax import Syntax  # type: ignore
    from rich.table import Table  # type: ignore
    from rich.text import Text  # type: ignore

    HAVE_RICH = True
except ModuleNotFoundError:  # pragma: no cover - utilizado en los tests
    import click

    HAVE_RICH = False

    class _BoxSentinel:
        """Objeto ligero usado para representar un estilo de borde inexistente."""

        def __init__(self, name: str):
            self.name = name

        def __repr__(self) -> str:  # pragma: no cover - salida auxiliar
            return f"<box {self.name}>"


    class _FallbackBox:
        """Tabla de estilos compatibles con la CLI cuando Rich no está disponible."""

        _KNOWN_NAMES = (
            "MINIMAL_DOUBLE_HEAD",
            "SQUARE",
            "MINIMAL",
            "SIMPLE_HEAVY",
        )

        def __init__(self) -> None:
            for name in self._KNOWN_NAMES:
                setattr(self, name, _BoxSentinel(name))

        def __getattr__(self, name: str) -> _BoxSentinel:
            sentinel = _BoxSentinel(name)
            setattr(self, name, sentinel)
            return sentinel

    box = _FallbackBox()

    class Text(str):
        """Representación de texto simple ignorando estilos."""

        def __new__(cls, text: str, style: str | None = None):  # noqa: D401 - misma firma
            return str.__new__(cls, text)


    @dataclass
    class Panel:
        """Panel simplificado que devuelve un bloque de texto plano."""

        renderable: object
        title: str | None = None
        border_style: str | None = None

        def __str__(self) -> str:  # pragma: no cover - trivial
            header = f"{self.title}\n" if self.title else ""
            return f"{header}{self.renderable}"

        @classmethod
        def fit(
            cls,
            renderable: object,
            title: str | None = None,
            border_style: str | None = None,
        ) -> "Panel":
            return cls(renderable=renderable, title=title, border_style=border_style)


    class Syntax(str):
        """Devuelve el propio código sin resaltado."""

        def __new__(cls, code: str, *_args, **_kwargs):  # noqa: D401 - misma firma
            return str.__new__(cls, code)


    class Table:
        """Tabla ASCII extremadamente básica para los casos de prueba."""

        def __init__(self, *_, **__):
            self._columns: list[str] = []
            self._rows: list[list[str]] = []

        def add_column(self, header: str | None, **_kwargs) -> None:
            self._columns.append(header or "")

        def add_row(self, *row: object) -> None:
            self._rows.append(["" if value is None else str(value) for value in row])

        @staticmethod
        def _calculate_widths(rows: Sequence[Sequence[str]]) -> list[int]:
            return [max(len(cell) for cell in column) for column in zip(*rows, strict=True)]

        def __str__(self) -> str:
            if not self._rows:
                return "\n".join(filter(None, self._columns))

            rows = self._rows
            columns = self._columns or [f"columna {idx + 1}" for idx in range(len(rows[0]))]

            matrix = [columns, *rows]
            widths = self._calculate_widths(matrix)

            def format_row(row: Sequence[str]) -> str:
                return " | ".join(cell.ljust(width) for cell, width in zip(row, widths, strict=True))

            header = format_row(columns)
            separator = "-+-".join("-" * width for width in widths)
            body = [format_row(row) for row in rows]
            return "\n".join([header, separator, *body])


    class Console:
        """Consola que imprime usando ``click.echo`` para capturar la salida."""

        def print(self, *objects: object, **_kwargs) -> None:
            for obj in objects:
                if obj is None:
                    continue
                click.echo(str(obj))


__all__ = [
    "HAVE_RICH",
    "Console",
    "Panel",
    "Syntax",
    "Table",
    "Text",
    "box",
]

