from __future__ import annotations

if __name__ == "__main__" and __package__ in {None, ""}:
    from pathlib import Path
    from runpy import run_module
    import sys

    package_root = Path(__file__).resolve().parent.parent
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    run_module("sqliteplus.cli", run_name="__main__")
    raise SystemExit()

import csv
import importlib
import importlib.metadata
import json
import math
import sqlite3
import webbrowser
from datetime import date, datetime, time
from decimal import Decimal
from itertools import islice
from numbers import Number
from pathlib import Path
from typing import Iterable

import click
import urllib.request

from sqliteplus.utils.rich_compat import Console, Panel, Syntax, Table, Text, box
from sqliteplus.utils.json_serialization import normalize_json_value as _normalize_json_value

from sqliteplus.utils.constants import DEFAULT_DB_PATH, resolve_default_db_path
from sqliteplus.utils.sqliteplus_sync import (
    SQLitePlus,
    SQLitePlusCipherError,
    SQLitePlusQueryError,
)
from sqliteplus.utils.replication_sync import SQLiteReplication
from sqliteplus.utils.profiling import run_with_optional_profiling


_VISUAL_EXTRA_INSTALL_COMMAND = 'pip install "sqliteplus-enhanced[visual]"'
_VISUAL_EXTRA_MESSAGE = (
    "La funcionalidad visual requiere instalar el extra opcional 'visual'. "
    f"Ejecuta '{_VISUAL_EXTRA_INSTALL_COMMAND}' antes de volver a intentarlo."
)


def _import_visual_viewer_dependencies():
    try:
        ft = importlib.import_module("flet")
        smart_table_module = importlib.import_module("fletplus.components.smart_table")
        style_module = importlib.import_module("fletplus.styles.style")
    except ModuleNotFoundError as exc:  # pragma: no cover - depende de extras opcionales
        raise click.ClickException(_VISUAL_EXTRA_MESSAGE) from exc

    return ft, smart_table_module.SmartTable, style_module.Style


def _import_visual_dashboard_dependencies():
    try:
        ft = importlib.import_module("flet")
        core_module = importlib.import_module("fletplus.core")
        context_module = importlib.import_module("fletplus.context")
        smart_table_module = importlib.import_module("fletplus.components.smart_table")
        style_module = importlib.import_module("fletplus.styles.style")
    except ModuleNotFoundError as exc:  # pragma: no cover - depende de extras opcionales
        raise click.ClickException(_VISUAL_EXTRA_MESSAGE) from exc

    return (
        core_module.FletPlusApp,
        smart_table_module.SmartTable,
        style_module.Style,
        context_module.theme_context,
        ft,
    )


def _resolve_fletplus_versions() -> dict[str, str | None]:
    version_info: dict[str, str | None] = {
        "installed": None,
        "latest": None,
        "error": None,
    }

    try:
        version_info["installed"] = importlib.metadata.version("fletplus")
    except importlib.metadata.PackageNotFoundError:
        version_info["error"] = "FletPlus no está instalado en el entorno actual."
        return version_info
    except Exception as exc:  # pragma: no cover - defensivo
        version_info["error"] = f"No se pudo detectar la versión instalada ({exc})."
        return version_info

    try:
        with urllib.request.urlopen("https://pypi.org/pypi/fletplus/json", timeout=5) as response:
            payload = json.loads(response.read().decode("utf-8"))
            version_info["latest"] = str(payload.get("info", {}).get("version"))
    except Exception:  # pragma: no cover - se degrada silenciosamente en modo offline
        version_info["error"] = "No se pudo comprobar la última versión en PyPI."

    return version_info


def _fetch_rows_respecting_limit(
    database: SQLitePlus, sql: str, max_rows: int
) -> tuple[list[str], list[tuple[object, ...]], bool]:
    """Ejecuta una consulta de solo lectura limitando las filas consumidas."""

    if max_rows <= 0:
        return [], [], False

    with database.lock:
        with database.get_connection() as conn:
            cursor = conn.cursor()
            try:
                cursor.execute(sql)
            except sqlite3.Error as exc:  # pragma: no cover - validado en tests existentes
                raise SQLitePlusQueryError(sql, exc) from exc

            column_names = [col[0] for col in cursor.description or []]
            # Consumimos una fila extra para detectar si la consulta tiene más resultados.
            fetched_rows = list(islice(cursor, max_rows + 1))
            truncated = len(fetched_rows) > max_rows
            if truncated:
                fetched_rows = fetched_rows[:max_rows]

            return column_names, fetched_rows, truncated


def _normalize_column_names(
    columns: list[str] | None,
    rows: Iterable[Iterable[object]] | None,
    *,
    placeholder_template: str = "columna_{index}",
) -> tuple[list[str], bool]:
    """Normaliza nombres de columna y detecta duplicados."""

    normalized_columns: list[str]
    if rows is None:
        materialized_rows: list[Iterable[object]] = []
    elif isinstance(rows, list):
        materialized_rows = rows
    else:
        materialized_rows = list(rows)

    if columns:
        normalized_columns = [
            column
            if column not in (None, "")
            else placeholder_template.format(index=index + 1)
            for index, column in enumerate(columns)
        ]
    elif materialized_rows:
        normalized_columns = [
            placeholder_template.format(index=index + 1)
            for index in range(len(materialized_rows[0]))
        ]
    else:
        normalized_columns = []

    has_duplicates = (
        len(set(normalized_columns)) != len(normalized_columns)
        if normalized_columns
        else False
    )

    return normalized_columns, has_duplicates


def _launch_fletplus_viewer(
    columns: list[str] | None,
    rows: Iterable[Iterable[object]],
    *,
    title: str = "Resultados de SQLitePlus",
    description: str | None = None,
    theme_mode: str = "system",
    page_size: int | None = None,
    virtualized: bool = False,
) -> None:
    """Abre un visor interactivo con FletPlus para mostrar los resultados."""

    ft, SmartTable, Style = _import_visual_viewer_dependencies()

    materialized_rows = [tuple(row) for row in rows]
    normalized_columns = (
        columns
        or [f"columna {index + 1}" for index in range(len(materialized_rows[0]))]
        if materialized_rows
        else ["columna 1"]
    )
    total_rows = len(materialized_rows)
    resolved_page_size = page_size or (10 if total_rows >= 10 else max(total_rows, 1))
    resolved_virtualized = virtualized and total_rows > resolved_page_size

    def _create_data_row(record: tuple[object, ...], font_size: int) -> ft.DataRow:
        return ft.DataRow(
            cells=[
                ft.DataCell(
                    ft.Text(
                        "NULL" if value is None else str(value),
                        selectable=True,
                        size=font_size,
                    )
                )
                for value in record
            ]
        )

    def main(page: ft.Page) -> None:
        theme_map = {
            "system": ft.ThemeMode.SYSTEM,
            "light": ft.ThemeMode.LIGHT,
            "dark": ft.ThemeMode.DARK,
        }
        page.title = title
        page.horizontal_alignment = ft.CrossAxisAlignment.STRETCH
        page.padding = 24
        page.scroll = ft.ScrollMode.AUTO
        page.theme_mode = theme_map.get(theme_mode.lower(), ft.ThemeMode.SYSTEM)

        font_size_state = {"value": 14}
        filtered_rows = materialized_rows.copy()

        def _data_provider(start: int, end: int) -> list[ft.DataRow]:
            subset = filtered_rows[start:end]
            return [_create_data_row(record, font_size_state["value"]) for record in subset]

        table = SmartTable(
            columns=normalized_columns,
            rows=None if resolved_virtualized else [
                _create_data_row(record, font_size_state["value"])
                for record in filtered_rows
            ],
            page_size=resolved_page_size,
            virtualized=resolved_virtualized,
            data_provider=_data_provider if resolved_virtualized else None,
            total_rows=len(filtered_rows),
            style=Style(
                bgcolor=ft.Colors.SURFACE_CONTAINER,
                border_radius=20,
                padding=ft.Padding(16, 20, 16, 24),
                shadow=ft.BoxShadow(
                    spread_radius=1,
                    blur_radius=22,
                    color=ft.Colors.with_opacity(0.18, ft.Colors.BLACK),
                ),
            ),
        )

        header = ft.Column(
            [
                ft.Text(title, weight=ft.FontWeight.BOLD, size=26),
                ft.Text(
                    description
                    or "Explora, ordena y navega por los datos devueltos por tu consulta.",
                    size=14,
                    opacity=0.75,
                ),
            ],
            spacing=4,
        )

        table_container = table.build()
        data_table = table_container.controls[0]

        footer_text = ft.Text(
            f"{len(filtered_rows)} fila(s) disponibles",
            size=12,
            italic=True,
            opacity=0.6,
        )

        theme_dropdown = ft.Dropdown(
            label="Tema visual",
            options=[
                ft.dropdown.Option("system", "Sistema"),
                ft.dropdown.Option("light", "Claro"),
                ft.dropdown.Option("dark", "Oscuro"),
            ],
            value=theme_mode.lower() if theme_mode else "system",
            on_change=lambda e: _set_theme(e.control.value or "system"),
            dense=True,
        )

        search_field = ft.TextField(
            label="Filtrar filas",
            hint_text="Introduce texto para filtrar las filas mostradas",
            prefix_icon=ft.Icons.SEARCH,
            on_change=lambda _: _apply_filters(),
            on_submit=lambda _: _apply_filters(),
            disabled=resolved_virtualized,
        )

        font_slider = ft.Slider(
            min=12,
            max=24,
            divisions=6,
            value=font_size_state["value"],
            label="{value} pt",
            on_change=lambda e: _update_font(int(e.control.value)),
            expand=True,
        )

        info_bar = ft.InfoBar(
            title=ft.Text("Modo virtual" if resolved_virtualized else "Modo local"),
            severity=ft.InfoBarSeverity.INFO,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.PRIMARY),
            content=ft.Text(
                "La búsqueda rápida está deshabilitada al virtualizar los datos."
                if resolved_virtualized
                else "Usa el filtro para localizar registros al instante.",
                size=12,
            ),
        )

        def _set_theme(value: str) -> None:
            page.theme_mode = theme_map.get(value.lower(), ft.ThemeMode.SYSTEM)
            page.update()

        def _update_table_rows() -> None:
            table.total_rows = len(filtered_rows)
            table.current_page = 0
            if resolved_virtualized:
                data_table.rows = table._get_page_rows()
            else:
                table.rows = [
                    _create_data_row(record, font_size_state["value"])
                    for record in filtered_rows
                ]
                data_table.rows = table._get_page_rows()
            footer_text.value = f"{len(filtered_rows)} fila(s) disponibles"
            footer_text.update()
            page.update()

        def _apply_filters() -> None:
            if resolved_virtualized:
                return
            query = (search_field.value or "").strip().lower()
            if not query:
                filtered_rows[:] = materialized_rows
            else:
                filtered_rows[:] = [
                    record
                    for record in materialized_rows
                    if any(
                        query in ("" if value is None else str(value).lower())
                        for value in record
                    )
                ]
            _update_table_rows()

        def _update_font(size: int) -> None:
            font_size_state["value"] = size
            if resolved_virtualized:
                data_table.rows = table._get_page_rows()
            else:
                for row in table.rows:
                    for cell in row.cells:
                        if hasattr(cell.content, "size"):
                            cell.content.size = size
                data_table.rows = table._get_page_rows()
            page.update()

        controls = [
            header,
            ft.ResponsiveRow(
                [
                    ft.Container(theme_dropdown, col=12, padding=0),
                    ft.Container(search_field, col=12, padding=0),
                    ft.Container(
                        ft.Column(
                            [
                                ft.Text("Tamaño de texto", size=12, opacity=0.7),
                                font_slider,
                            ]
                        ),
                        col=12,
                    ),
                ],
                run_spacing=12,
            ),
            info_bar,
            table_container,
            footer_text,
        ]

        page.add(ft.Column(controls=controls, expand=True, spacing=18))

    ft.app(target=main)


def _coerce_numeric(value: object) -> float | None:
    """Intenta convertir ``value`` en un flotante utilizable para estadísticas."""

    if value is None or isinstance(value, bool):
        return None
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, Number) and not isinstance(value, complex):
        return float(value)
    if isinstance(value, str):
        candidate = value.strip().replace(",", ".")
        if not candidate:
            return None
        try:
            return float(candidate)
        except ValueError:
            return None
    return None


def _format_numeric(value: float) -> str:
    """Devuelve una cadena amigable para mostrar métricas numéricas."""

    if not math.isfinite(value):
        return str(value)

    precision = 4 if abs(value) < 1000 else 2
    decimal_separator = "."
    thousands_separator = "\u202f"

    formatted = format(value, f".{precision}f")

    sign = ""
    if formatted.startswith("-"):
        sign = "-"
        formatted = formatted[1:]

    integer_part, _, fractional_part = formatted.partition(".")
    grouped_integer = "{:,}".format(int(integer_part or "0")).replace(",", thousands_separator)

    return f"{sign}{grouped_integer}{decimal_separator}{fractional_part}"


console = Console()


@click.group()
@click.option(
    "--cipher-key",
    envvar="SQLITE_DB_KEY",
    help="Clave SQLCipher a utilizar al abrir las bases de datos.",
)
@click.option(
    "--db-path",
    default=DEFAULT_DB_PATH,
    show_default=True,
    type=click.Path(dir_okay=False, resolve_path=True, path_type=str),
    help=(
        "Ruta del archivo de base de datos a utilizar en todos los comandos. "
        "Si no se indica, se creará en ./sqliteplus/databases/database.db "
        "respecto al directorio actual."
    ),
)
@click.pass_context
def cli(ctx, cipher_key, db_path):
    """Herramientas de consola para trabajar con SQLitePlus sin programar."""
    ctx.ensure_object(dict)
    ctx.obj["cipher_key"] = cipher_key
    normalized_db_path = Path(db_path).expanduser()
    if normalized_db_path == Path(DEFAULT_DB_PATH):
        normalized_db_path = resolve_default_db_path(prefer_package=False)
    ctx.obj["db_path"] = str(Path(normalized_db_path).expanduser().resolve())
    ctx.obj["console"] = console


@click.command(help="Crea la base de datos si no existe y registra la acción en el historial.")
@click.pass_context
def init_db(ctx):
    """Inicializa la base de datos SQLitePlus."""
    db = SQLitePlus(
        db_path=ctx.obj.get("db_path"),
        cipher_key=ctx.obj.get("cipher_key"),
    )
    db.log_action("Inicialización de la base de datos desde CLI")
    panel = Panel.fit(
        Text(f"Base de datos preparada en {db.db_path}.", style="bold green"),
        title="SQLitePlus listo",
        border_style="green",
    )
    ctx.obj["console"].print(panel)


@click.command(help="Ejecuta instrucciones de inserción, actualización o borrado.")
@click.argument("query", nargs=-1, required=True)
@click.pass_context
def execute(ctx, query):
    """Ejecuta una consulta SQL de escritura."""
    sql = " ".join(query)
    db = SQLitePlus(
        db_path=ctx.obj.get("db_path"),
        cipher_key=ctx.obj.get("cipher_key"),
    )
    try:
        result = db.execute_query(sql)
    except SQLitePlusQueryError as exc:
        raise click.ClickException(str(exc)) from exc
    except SQLitePlusCipherError as exc:
        raise click.ClickException(str(exc)) from exc

    lines = ["[bold green]Consulta ejecutada correctamente.[/bold green]"]
    if result is not None:
        lines.append(f"[cyan]ID insertado: {result}[/cyan]")

    ctx.obj["console"].print(
        Panel.fit(
            "\n".join(lines),
            border_style="green",
            title="Operación completada",
        )
    )


@click.command(help="Recupera datos y los muestra en pantalla fila por fila.")
@click.option(
    "--limit",
    type=click.IntRange(1),
    default=None,
    help="Limita el número de filas mostradas sin modificar la consulta original.",
)
@click.option(
    "--output",
    type=click.Choice(["table", "json", "plain"], case_sensitive=False),
    default="table",
    show_default=True,
    help="Formato de salida accesible a tus necesidades.",
)
@click.option(
    "--viewer/--no-viewer",
    "show_viewer",
    default=False,
    help=(
        "Abre un visor interactivo con FletPlus para explorar el resultado. "
        f"Requiere '{_VISUAL_EXTRA_INSTALL_COMMAND}'."
    ),
)
@click.option(
    "--viewer-theme",
    type=click.Choice(["system", "light", "dark"], case_sensitive=False),
    default="system",
    show_default=True,
    help="Tema inicial utilizado en el visor interactivo.",
)
@click.option(
    "--viewer-page-size",
    type=click.IntRange(5, 100),
    default=15,
    show_default=True,
    help="Filas por página dentro del visor visual.",
)
@click.option(
    "--viewer-virtual/--viewer-materialized",
    "viewer_virtualized",
    default=False,
    help="Activa la carga virtual de filas en el visor para conjuntos muy grandes.",
)
@click.option(
    "--summary/--no-summary",
    "show_summary",
    default=False,
    help="Calcula un resumen estadístico rápido para columnas numéricas.",
)
@click.argument("query", nargs=-1, required=True)
@click.pass_context
def fetch(
    ctx,
    limit,
    output,
    show_viewer,
    viewer_theme,
    viewer_page_size,
    viewer_virtualized,
    show_summary,
    query,
):
    """Ejecuta una consulta SQL de lectura."""
    sql = " ".join(query)
    db = SQLitePlus(
        db_path=ctx.obj.get("db_path"),
        cipher_key=ctx.obj.get("cipher_key"),
    )
    try:
        columns, result = db.fetch_query_with_columns(sql)
    except SQLitePlusQueryError as exc:
        raise click.ClickException(str(exc)) from exc
    except SQLitePlusCipherError as exc:
        raise click.ClickException(str(exc)) from exc

    console_obj = ctx.obj["console"]
    total_rows = len(result)
    displayed_rows = list(result)
    truncated = False
    if limit is not None and total_rows > limit:
        displayed_rows = displayed_rows[:limit]
        truncated = True

    if not displayed_rows:
        console_obj.print(
            Panel.fit(
                Text("No se encontraron filas.", style="bold yellow"),
                title="Consulta vacía",
                border_style="yellow",
            )
        )
        return

    displayed_rows = [tuple(row) for row in displayed_rows]

    normalized_columns, has_duplicate_column_names = _normalize_column_names(
        columns,
        displayed_rows,
        placeholder_template="columna {index}",
    )

    if output.lower() == "json":
        json_ready_rows = [
            tuple(_normalize_json_value(value) for value in row)
            for row in displayed_rows
        ]
        if not normalized_columns:
            payload = [list(row) for row in json_ready_rows]
        elif has_duplicate_column_names:
            payload = {
                "columns": normalized_columns,
                "rows": [list(row) for row in json_ready_rows],
            }
        else:
            payload = [
                {normalized_columns[idx]: row[idx] for idx in range(len(row))}
                for row in json_ready_rows
            ]
        json_text = json.dumps(payload, ensure_ascii=False, indent=2)
        console_obj.print(
            Panel(
                Syntax(json_text, "json", indent_guides=True),
                title="Resultado JSON",
                border_style="blue",
            )
        )
    elif output.lower() == "plain":
        lines = []
        if normalized_columns:
            lines.append(" | ".join(normalized_columns))
        for row in displayed_rows:
            lines.append(" | ".join("NULL" if value is None else str(value) for value in row))
        console_obj.print(
            Panel.fit(
                Text("\n".join(lines), style="bold white"),
                title="Resultado plano",
                border_style="cyan",
            )
        )
    else:
        table = Table(box=box.MINIMAL_DOUBLE_HEAD, title="Resultados", header_style="bold magenta")
        if normalized_columns:
            for column in normalized_columns:
                table.add_column(column, overflow="fold")

        for row in displayed_rows:
            table.add_row(*("NULL" if value is None else str(value) for value in row))

        console_obj.print(table)

    footer_message = f"[green]{len(displayed_rows)}[/green] fila(s) mostradas"
    if truncated:
        footer_message += f" de un total de {total_rows}. Usa --limit para ajustar."
    console_obj.print(footer_message)

    if show_summary and normalized_columns:
        numeric_summary: list[tuple[str, int, float, float, float]] = []
        for index, column_name in enumerate(normalized_columns):
            numeric_values: list[float] = []
            for row in displayed_rows:
                if index >= len(row):
                    continue
                coerced = _coerce_numeric(row[index])
                if coerced is not None:
                    numeric_values.append(coerced)
            if numeric_values:
                numeric_summary.append(
                    (
                        column_name,
                        len(numeric_values),
                        min(numeric_values),
                        sum(numeric_values) / len(numeric_values),
                        max(numeric_values),
                    )
                )

        if numeric_summary:
            summary_table = Table(
                title="Resumen numérico",
                header_style="bold blue",
                box=box.MINIMAL_DOUBLE_HEAD,
            )
            summary_table.add_column("Columna", style="bold")
            summary_table.add_column("Valores", justify="right")
            summary_table.add_column("Mínimo", justify="right")
            summary_table.add_column("Promedio", justify="right")
            summary_table.add_column("Máximo", justify="right")

            for name, count, minimum, average, maximum in numeric_summary:
                summary_table.add_row(
                    name,
                    str(count),
                    _format_numeric(minimum),
                    _format_numeric(average),
                    _format_numeric(maximum),
                )

            console_obj.print(summary_table)
        else:
            console_obj.print(
                Panel.fit(
                    Text(
                        "No se detectaron columnas numéricas para generar estadísticas.",
                        style="bold yellow",
                    ),
                    border_style="yellow",
                    title="Resumen no disponible",
                )
            )

    if show_viewer:
        console_obj.print(
            Panel.fit(
                Text(
                    "Abriendo visor interactivo FletPlus. Cierra la ventana para volver a la terminal.",
                    style="bold cyan",
                ),
                border_style="cyan",
                title="Modo interactivo",
            )
        )
        _launch_fletplus_viewer(
            normalized_columns or None,
            displayed_rows,
            title="Resultados de la consulta",
            description="Visualiza y filtra los datos devueltos por la sentencia SQL.",
            theme_mode=viewer_theme,
            page_size=viewer_page_size,
            virtualized=viewer_virtualized,
        )


@click.command(help="Guarda una tabla como archivo CSV para compartirla fácilmente.")
@click.argument("table_name")
@click.argument("output_file")
@click.option(
    "--db-path",
    default=None,
    show_default=False,
    type=click.Path(dir_okay=False, resolve_path=True, path_type=str),
    help="Ruta específica de la base que quieres exportar (por defecto usa la global).",
)
@click.option(
    "--overwrite/--no-overwrite",
    default=False,
    help="Permite sobrescribir el archivo de salida si ya existe.",
)
@click.pass_context
def export_csv(ctx, table_name, output_file, db_path, overwrite):
    """Exporta una tabla a CSV."""
    resolved_db_path = db_path or ctx.obj.get("db_path")
    replicator = SQLiteReplication(
        db_path=resolved_db_path,
        cipher_key=ctx.obj.get("cipher_key"),
    )
    try:
        export_path = replicator.export_to_csv(
            table_name, output_file, overwrite=overwrite
        )
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="table_name") from exc
    except FileExistsError as exc:
        raise click.ClickException(str(exc)) from exc
    except sqlite3.Error as exc:
        raise click.ClickException(str(exc)) from exc
    except (SQLitePlusCipherError, RuntimeError) as exc:
        raise click.ClickException(str(exc)) from exc

    ctx.obj["console"].print(
        Panel.fit(
            Text(
                f"Tabla {table_name} exportada a {export_path}",
                style="bold green",
            ),
            title="Exportación completada",
            border_style="green",
        )
    )


@click.command(
    name="export-query",
    help="Ejecuta una consulta de lectura y exporta el resultado a JSON o CSV.",
)
@click.option(
    "--format",
    "export_format",
    type=click.Choice(["json", "csv"], case_sensitive=False),
    default="json",
    show_default=True,
    help="Formato de exportación del resultado.",
)
@click.option(
    "--limit",
    type=click.IntRange(1),
    default=None,
    help="Limita el número de filas exportadas sin modificar la consulta.",
)
@click.option(
    "--overwrite/--no-overwrite",
    default=False,
    help="Permite sobrescribir el archivo de salida si ya existe.",
)
@click.argument(
    "output_file",
    type=click.Path(dir_okay=False, writable=True, resolve_path=True, path_type=str),
)
@click.argument("query", nargs=-1, required=True)
@click.pass_context
def export_query(ctx, export_format, limit, overwrite, output_file, query):
    """Exporta el resultado de una consulta SELECT a un archivo."""

    sql = " ".join(query)
    path = Path(output_file)
    if path.exists() and not overwrite:
        raise click.ClickException(
            "El archivo de salida ya existe. Usa --overwrite para reemplazarlo."
        )

    path.parent.mkdir(parents=True, exist_ok=True)

    db = SQLitePlus(
        db_path=ctx.obj.get("db_path"),
        cipher_key=ctx.obj.get("cipher_key"),
    )

    try:
        columns, rows = db.fetch_query_with_columns(sql)
    except (SQLitePlusCipherError, SQLitePlusQueryError) as exc:
        raise click.ClickException(str(exc)) from exc

    if limit is not None:
        rows = rows[:limit]

    normalized_columns, has_duplicate_column_names = _normalize_column_names(
        columns,
        rows,
        placeholder_template="columna_{index}",
    )

    if export_format.lower() == "json":
        json_ready_rows = [
            tuple(_normalize_json_value(value) for value in row)
            for row in rows
        ]

        if not normalized_columns:
            payload = [list(row) for row in json_ready_rows]
        elif has_duplicate_column_names:
            payload = {
                "columns": normalized_columns,
                "rows": [list(row) for row in json_ready_rows],
            }
        else:
            payload = [
                {normalized_columns[idx]: row[idx] for idx in range(len(row))}
                for row in json_ready_rows
            ]
        path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    else:
        with path.open("w", encoding="utf-8", newline="") as file_handle:
            writer = csv.writer(file_handle)
            if normalized_columns:
                writer.writerow(normalized_columns)
            for row in rows:
                writer.writerow(["" if value is None else value for value in row])

    ctx.obj["console"].print(
        Panel.fit(
            Text(
                f"Consulta exportada en formato {export_format.upper()} a {path}.",
                style="bold green",
            ),
            title="Exportación completada",
            border_style="green",
        )
    )


@click.command(help="Genera un respaldo fechado de la base indicada.")
@click.option(
    "--db-path",
    default=None,
    show_default=False,
    type=click.Path(dir_okay=False, resolve_path=True, path_type=str),
    help="Ruta específica de la base a respaldar (por defecto usa la global).",
)
@click.pass_context
def backup(ctx, db_path):
    """Crea un respaldo de la base de datos."""
    resolved_db_path = db_path or ctx.obj.get("db_path")
    replicator = SQLiteReplication(
        db_path=resolved_db_path,
        cipher_key=ctx.obj.get("cipher_key"),
    )
    try:
        backup_path = replicator.backup_database()
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    ctx.obj["console"].print(
        Panel.fit(
            Text(
                f"Respaldo disponible en {backup_path}.",
                style="bold green",
            ),
            title="Respaldo generado",
            border_style="green",
        )
    )


@click.command(name="list-tables", help="Muestra las tablas disponibles y su número de filas.")
@click.option(
    "--include-views/--exclude-views",
    default=False,
    help="Incluye vistas dentro del listado.",
)
@click.option(
    "--viewer/--no-viewer",
    "show_viewer",
    default=False,
    help=(
        "Abre una vista enriquecida con FletPlus para explorar el inventario. "
        f"Requiere '{_VISUAL_EXTRA_INSTALL_COMMAND}'."
    ),
)
@click.option(
    "--viewer-theme",
    type=click.Choice(["system", "light", "dark"], case_sensitive=False),
    default="system",
    show_default=True,
    help="Tema inicial del visor visual.",
)
@click.option(
    "--viewer-page-size",
    type=click.IntRange(5, 50),
    default=12,
    show_default=True,
    help="Filas por página dentro del visor visual.",
)
@click.pass_context
def list_tables(ctx, include_views, show_viewer, viewer_theme, viewer_page_size):
    """Lista las tablas de la base de datos actual."""

    db = SQLitePlus(
        db_path=ctx.obj.get("db_path"),
        cipher_key=ctx.obj.get("cipher_key"),
    )

    try:
        tables = db.list_tables(include_views=include_views, include_row_counts=True)
    except (SQLitePlusCipherError, SQLitePlusQueryError) as exc:
        raise click.ClickException(str(exc)) from exc

    console_obj = ctx.obj["console"]
    if not tables:
        console_obj.print(
            Panel.fit(
                Text("No se encontraron tablas en la base de datos.", style="bold yellow"),
                title="Sin resultados",
                border_style="yellow",
            )
        )
        return

    table = Table(
        title="Tablas disponibles",
        header_style="bold cyan",
        box=box.SQUARE,
    )
    table.add_column("Nombre", style="bold")
    table.add_column("Tipo", style="magenta")
    table.add_column("Filas", justify="right")

    for item in tables:
        row_count = "-" if item["row_count"] is None else f"{item['row_count']:,}".replace(",", ".")
        table.add_row(item["name"], item["type"].title(), row_count)

    console_obj.print(table)

    total_tables = sum(1 for item in tables if item["type"] == "table")
    total_views = sum(1 for item in tables if item["type"] == "view")
    known_counts = [item["row_count"] for item in tables if item["row_count"] is not None]
    summary = Table(show_header=False, box=box.MINIMAL)
    summary.add_row("Tablas", str(total_tables))
    summary.add_row("Vistas", str(total_views))
    if known_counts:
        total_count = sum(known_counts)
        summary.add_row("Filas conocidas", f"{total_count:,}".replace(",", "."))

    console_obj.print(
        Panel(summary, title="Resumen de objetos", border_style="cyan")
    )

    if show_viewer:
        console_obj.print(
            Panel.fit(
                Text(
                    "Abriendo catálogo interactivo para navegar por tablas y vistas.",
                    style="bold cyan",
                ),
                border_style="cyan",
                title="Modo visual",
            )
        )
        viewer_rows = [
            (
                item["name"],
                "Tabla" if item["type"] == "table" else "Vista",
                item["row_count"] if item["row_count"] is not None else "(sin dato)",
            )
            for item in tables
        ]
        _launch_fletplus_viewer(
            ["Nombre", "Tipo", "Filas"],
            viewer_rows,
            title="Inventario de objetos",
            description="Consulta de forma accesible las tablas y vistas disponibles.",
            theme_mode=viewer_theme,
            page_size=viewer_page_size,
        )


@click.command(name="describe-table", help="Detalla la estructura de una tabla existente.")
@click.argument("table_name")
@click.pass_context
def describe_table(ctx, table_name):
    """Describe columnas, índices y claves foráneas de la tabla."""

    db = SQLitePlus(
        db_path=ctx.obj.get("db_path"),
        cipher_key=ctx.obj.get("cipher_key"),
    )

    try:
        details = db.describe_table(table_name)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="table_name") from exc
    except (SQLitePlusCipherError, SQLitePlusQueryError) as exc:
        raise click.ClickException(str(exc)) from exc

    console_obj = ctx.obj["console"]

    summary = Table(box=box.MINIMAL, show_header=False)
    summary.add_row("Tabla", table_name)
    if details["row_count"] is not None:
        summary.add_row("Filas", f"{details['row_count']:,}".replace(",", "."))

    console_obj.print(Panel(summary, title="Resumen", border_style="cyan"))

    columns_table = Table(
        title="Columnas",
        header_style="bold magenta",
        box=box.MINIMAL_DOUBLE_HEAD,
    )
    columns_table.add_column("Nombre", style="bold")
    columns_table.add_column("Tipo")
    columns_table.add_column("Nulo", justify="center")
    columns_table.add_column("Predeterminado")
    columns_table.add_column("PK", justify="center")

    for column in details["columns"]:
        columns_table.add_row(
            column["name"],
            column["type"] or "",
            "No" if column["notnull"] else "Sí",
            str(column["default"]) if column["default"] is not None else "",
            "Sí" if column["pk"] else "No",
        )

    console_obj.print(columns_table)

    if details["indexes"]:
        indexes_table = Table(
            title="Índices",
            header_style="bold blue",
            box=box.MINIMAL_DOUBLE_HEAD,
        )
        indexes_table.add_column("Nombre", style="bold")
        indexes_table.add_column("Único", justify="center")
        indexes_table.add_column("Origen")
        indexes_table.add_column("Parcial", justify="center")

        for index in details["indexes"]:
            indexes_table.add_row(
                index["name"],
                "Sí" if index["unique"] else "No",
                index["origin"],
                "Sí" if index["partial"] else "No",
            )

        console_obj.print(indexes_table)

    if details["foreign_keys"]:
        fk_table = Table(
            title="Claves foráneas",
            header_style="bold yellow",
            box=box.MINIMAL_DOUBLE_HEAD,
        )
        fk_table.add_column("Columna", style="bold")
        fk_table.add_column("Tabla destino")
        fk_table.add_column("Columna destino")
        fk_table.add_column("ON UPDATE")
        fk_table.add_column("ON DELETE")

        for fk in details["foreign_keys"]:
            fk_table.add_row(
                fk["from"],
                fk["table"],
                fk["to"],
                fk["on_update"],
                fk["on_delete"],
            )

        console_obj.print(fk_table)


@click.command(name="db-info", help="Resumen general del archivo de base de datos actual.")
@click.pass_context
def database_info(ctx):
    """Muestra estadísticas del archivo SQLite en uso."""

    db = SQLitePlus(
        db_path=ctx.obj.get("db_path"),
        cipher_key=ctx.obj.get("cipher_key"),
    )

    try:
        stats = db.get_database_statistics()
    except (SQLitePlusCipherError, SQLitePlusQueryError) as exc:
        raise click.ClickException(str(exc)) from exc

    console_obj = ctx.obj["console"]
    info_table = Table(show_header=False, box=box.SIMPLE_HEAVY)
    info_table.add_row("Ruta", stats["path"])
    info_table.add_row("Tamaño", f"{stats['size_in_bytes'] / 1024:.1f} KB")
    if stats["last_modified"]:
        info_table.add_row("Modificación", stats["last_modified"].strftime("%Y-%m-%d %H:%M:%S"))
    info_table.add_row("Tablas", str(stats["table_count"]))
    info_table.add_row("Vistas", str(stats["view_count"]))
    info_table.add_row("Filas totales", str(stats["total_rows"]))

    console_obj.print(Panel(info_table, title="Base de datos", border_style="magenta"))

@click.command(
    name="visual-dashboard",
    help=(
        "Abre un panel visual construido con FletPlus para explorar la base. "
        f"Requiere '{_VISUAL_EXTRA_INSTALL_COMMAND}'."
    ),
)
@click.option(
    "--include-views/--exclude-views",
    default=True,
    show_default=True,
    help="Incluye vistas dentro del panel de resumen.",
)
@click.option(
    "--read-only/--allow-write",
    default=True,
    show_default=True,
    help="Controla si la sección de consultas permite operaciones de escritura.",
)
@click.option(
    "--max-rows",
    type=click.IntRange(10, 2000),
    default=200,
    show_default=True,
    help="Número máximo de filas a renderizar en la vista visual.",
)
@click.option(
    "--theme",
    type=click.Choice(["system", "light", "dark"], case_sensitive=False),
    default="system",
    show_default=True,
    help="Tema inicial del panel visual.",
)
@click.option(
    "--accent-color",
    default="BLUE_400",
    show_default=True,
    help="Color primario para resaltar métricas en el panel.",
)
@click.pass_context
def visual_dashboard(ctx, include_views, read_only, max_rows, theme, accent_color):
    """Lanza una experiencia accesible e interactiva usando la librería FletPlus."""

    FletPlusApp, SmartTable, Style, theme_context, ft = _import_visual_dashboard_dependencies()

    version_info = _resolve_fletplus_versions()

    db_path = ctx.obj.get("db_path")
    cipher_key = ctx.obj.get("cipher_key")

    def _resolve_color_name(name: str, fallback: str) -> str:
        if not name:
            return fallback
        candidate = name.strip().upper()
        color_value = getattr(ft.Colors, candidate, None)
        if color_value:
            return color_value
        if name.startswith("#"):
            return name
        return fallback

    resolved_theme = theme.lower() if theme else "system"
    primary_color = _resolve_color_name(accent_color, ft.Colors.BLUE_400)
    theme_state = {"mode": resolved_theme, "accent": primary_color}
    commands = {}

    theme_config: dict[str, object] = {
        "tokens": {
            "primary": primary_color,
            "secondary": ft.Colors.PURPLE_200,
            "surface": ft.Colors.SURFACE,
        }
    }

    if resolved_theme in {"light", "dark"}:
        theme_config["palette_mode"] = resolved_theme

    def _open_docs() -> None:
        documentation_path = Path(__file__).resolve().parent.parent / "docs" / "index.md"
        target = documentation_path.as_uri() if documentation_path.exists() else "https://pypi.org/project/sqliteplus-enhanced/"
        webbrowser.open(target)

    commands["Abrir documentación de SQLitePlus"] = _open_docs
    commands["Visitar FletPlus en PyPI"] = lambda: webbrowser.open("https://pypi.org/project/fletplus/")

    theme_status_text = ft.Text(
        "Tema sincronizado con la preferencia del sistema" if resolved_theme == "system" else f"Tema inicial: {resolved_theme}",
        size=12,
        opacity=0.85,
        selectable=True,
    )

    accent_swatch: ft.Container | None = None
    theme_status_container: ft.Container | None = None
    accent_input: ft.TextField | None = None
    mode_selector: ft.Dropdown | None = None
    accent_presets = {
        "Índigo": ft.Colors.INDIGO_400,
        "Cian": ft.Colors.CYAN_400,
        "Esmeralda": ft.Colors.GREEN_400,
        "Lavanda": ft.Colors.PURPLE_200,
    }

    def _refresh_theme_helper_labels() -> None:
        mode_label = {
            "system": "Sistema",
            "light": "Claro",
            "dark": "Oscuro",
        }.get(theme_state["mode"], theme_state["mode"])
        theme_status_text.value = (
            f"Tema: {mode_label} • Acento: {theme_state['accent']}"
        )
        if accent_swatch is not None:
            accent_swatch.bgcolor = theme_state["accent"]
            accent_swatch.update()
        if theme_status_container is not None:
            theme_status_container.bgcolor = ft.Colors.with_opacity(
                0.04, theme_state["accent"]
            )
            theme_status_container.update()
        theme_status_text.update()

    def _apply_theme_change(page: "ft.Page", *, palette_mode: str | None = None, accent: str | None = None) -> None:
        nonlocal theme_config, primary_color
        theme_manager = None
        try:
            theme_manager = theme_context.get(None)
        except Exception:
            theme_manager = None

        if palette_mode:
            theme_state["mode"] = palette_mode
            if palette_mode == "system":
                theme_config.pop("palette_mode", None)
                if theme_manager:
                    theme_manager.set_follow_platform_theme(True, apply_current=True)
            else:
                theme_config["palette_mode"] = palette_mode
                if theme_manager:
                    theme_manager.set_follow_platform_theme(False, apply_current=False)
                    theme_manager.set_dark_mode(palette_mode == "dark")

        if accent:
            theme_state["accent"] = accent
            theme_config.setdefault("tokens", {})["primary"] = accent
            primary_color = accent
            if theme_manager:
                theme_manager.set_token("colors.primary", accent)
                theme_manager.set_token("colors.accent", accent)

        if theme_manager:
            try:
                page.update()
            except Exception:
                pass
        _refresh_theme_helper_labels()

    def _handle_theme_mode_change(event):
        selected = (event.control.value or "system").lower()
        _apply_theme_change(event.page, palette_mode=selected)

    def _handle_accent_submit(event):
        new_color = _resolve_color_name(event.control.value or "", theme_state["accent"])
        event.control.value = new_color
        event.control.update()
        _apply_theme_change(event.page, accent=new_color)

    def _handle_accent_preset(event):
        selected = event.control.value
        if selected and selected in accent_presets:
            new_color = accent_presets[selected]
            if accent_input is not None:
                accent_input.value = new_color
                accent_input.update()
            _apply_theme_change(event.page, accent=new_color)

    _refresh_theme_helper_labels()

    def build_theme_controls() -> ft.Control:
        nonlocal accent_swatch, accent_input, mode_selector

        mode_selector = ft.Dropdown(
            label="Tema de la app",
            value=theme_state["mode"],
            options=[
                ft.dropdown.Option("system", "Seguir sistema"),
                ft.dropdown.Option("light", "Modo claro"),
                ft.dropdown.Option("dark", "Modo oscuro"),
            ],
            width=220,
            on_change=_handle_theme_mode_change,
            tooltip="Aplica la variante de tema sin recargar la vista",
        )

        accent_swatch = ft.Container(
            width=28,
            height=28,
            bgcolor=theme_state["accent"],
            border_radius=8,
            border=ft.border.all(1, ft.Colors.with_opacity(0.12, ft.Colors.BLACK)),
        )

        accent_input = ft.TextField(
            label="Color primario",
            value=theme_state["accent"],
            hint_text="Ej: #6750A4 o BLUE_400",
            prefix_icon=ft.Icons.COLOR_LENS,
            on_submit=_handle_accent_submit,
            width=260,
            tooltip="Introduce un color o nombre de token de Flet para actualizar la paleta",
        )

        accent_selector = ft.Dropdown(
            label="Paleta rápida",
            options=[ft.dropdown.Option(key) for key in accent_presets],
            width=180,
            on_change=_handle_accent_preset,
            tooltip="Aplica combinaciones de acento preparadas",
        )

        color_row = ft.Row(
            controls=[accent_input, accent_selector, accent_swatch],
            spacing=12,
            vertical_alignment=ft.CrossAxisAlignment.END,
        )

        _refresh_theme_helper_labels()

        return ft.Container(
            content=ft.Column(
                [
                    ft.Text(
                        "Personaliza tema y acento sin salir del panel.",
                        weight=ft.FontWeight.W_600,
                    ),
                    ft.ResponsiveRow(
                        [
                            ft.Container(content=mode_selector, col=12, md=6),
                            ft.Container(content=color_row, col=12, md=6),
                        ],
                        columns=12,
                        run_spacing=10,
                    ),
                    theme_status_text,
                ],
                spacing=8,
            ),
            padding=ft.Padding(14, 12, 14, 12),
            border_radius=12,
            bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.ON_SURFACE),
        )

    def _apply_preset(event, target_field, preset_map):
        selected = event.control.value
        if selected and selected in preset_map:
            target_field.value = preset_map[selected]
            target_field.update()

    def build_summary_view():
        database = SQLitePlus(db_path=db_path, cipher_key=cipher_key)
        stats = database.get_database_statistics(include_views=include_views)
        tables = database.list_tables(include_views=include_views, include_row_counts=True)

        def _build_version_notice() -> ft.InfoBar:
            installed = version_info.get("installed")
            latest = version_info.get("latest")
            error_message = version_info.get("error")

            severity = ft.InfoBarSeverity.INFO
            title = ft.Text("Estado de FletPlus")
            content_text = ""
            actions: list[ft.Control] = []

            if installed:
                content_text = f"Versión instalada: {installed}."
                if latest:
                    if latest != installed:
                        severity = ft.InfoBarSeverity.WARNING
                        content_text += f" Disponible en PyPI: {latest}."
                        actions.append(
                            ft.TextButton(
                                "Ver en PyPI",
                                url="https://pypi.org/project/fletplus/",
                                tooltip="Abrir PyPI en el navegador",
                            )
                        )
                    else:
                        severity = ft.InfoBarSeverity.SUCCESS
                        content_text += " Estás al día con la última versión."
                else:
                    content_text += " No se pudo comprobar la versión más reciente en PyPI."
            else:
                severity = ft.InfoBarSeverity.ERROR
                content_text = error_message or "No se pudo determinar la instalación de FletPlus."
                actions.append(
                    ft.TextButton(
                        "PyPI",
                        url="https://pypi.org/project/fletplus/",
                        tooltip="Abrir el proyecto en PyPI",
                    )
                )

            return ft.InfoBar(
                title=title,
                severity=severity,
                content=ft.Text(content_text, size=12),
                actions=actions,
                open=True,
            )

        def tinted(color: str, opacity: float = 0.18) -> str:
            try:
                return ft.Colors.with_opacity(opacity, color)
            except Exception:
                return color

        highlight_palette = [
            ("Tablas", str(stats["table_count"]), tinted(primary_color)),
            ("Vistas", str(stats["view_count"]), tinted(ft.Colors.PURPLE_200)),
            (
                "Filas totales",
                f"{stats['total_rows']:,}".replace(",", "."),
                tinted(ft.Colors.GREEN_300),
            ),
            (
                "Tamaño",
                f"{stats['size_in_bytes'] / 1024:.1f} KB",
                tinted(ft.Colors.AMBER_200),
            ),
        ]

        cards = ft.ResponsiveRow(
            [
                ft.Container(
                    content=ft.Column(
                        [
                            ft.Text(label, size=16, weight=ft.FontWeight.W_600),
                            ft.Text(value, size=26, weight=ft.FontWeight.BOLD),
                        ],
                        spacing=4,
                    ),
                    bgcolor=color,
                    padding=16,
                    border_radius=12,
                    col=12 if idx >= 2 else 6,
                )
                for idx, (label, value, color) in enumerate(highlight_palette)
            ],
            vertical_alignment=ft.CrossAxisAlignment.START,
        )

        header_notice = ft.InfoBar(
            title=ft.Text("Accesibilidad mejorada"),
            severity=ft.InfoBarSeverity.SUCCESS,
            content=ft.Text(
                "Ajusta tema y color desde la sección superior o la CLI y usa Ctrl+K para abrir la paleta de comandos.",
                size=12,
            ),
            open=True,
        )

        theme_controls = build_theme_controls()

        summary_columns = ["Nombre", "Tipo", "Filas"]

        def _summary_row(table_item: dict) -> ft.DataRow:
            return ft.DataRow(
                cells=[
                    ft.DataCell(ft.Text(table_item["name"])),
                    ft.DataCell(
                        ft.Text("Tabla" if table_item["type"] == "table" else "Vista")
                    ),
                    ft.DataCell(
                        ft.Text(
                            "NULL"
                            if table_item["row_count"] is None
                            else f"{table_item['row_count']:,}".replace(",", ".")
                        )
                    ),
                ]
            )

        summary_rows = [_summary_row(item) for item in tables]
        summary_virtualized = len(summary_rows) > 10

        summary_table = SmartTable(
            columns=summary_columns,
            rows=None if summary_virtualized else summary_rows,
            total_rows=len(summary_rows),
            page_size=10,
            virtualized=summary_virtualized,
            data_provider=(
                lambda start, end: [_summary_row(item) for item in tables[start:end]]
                if summary_virtualized
                else None
            ),
            style=Style(
                bgcolor=ft.Colors.SURFACE,
                border_radius=14,
                padding=ft.Padding(12, 14, 12, 16),
                shadow=ft.BoxShadow(
                    spread_radius=0,
                    blur_radius=18,
                    color=ft.Colors.with_opacity(0.14, ft.Colors.BLACK),
                ),
            ),
        )

        summary_table_container = summary_table.build()

        tables_section = ft.Column(
            [
                ft.Text("Objetos disponibles", weight=ft.FontWeight.BOLD, size=18),
                ft.Divider(),
                summary_table_container,
            ],
            spacing=8,
        )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("SQLitePlus Studio", size=24, weight=ft.FontWeight.BOLD),
                    ft.Text(f"Ruta actual: {stats['path']}", selectable=True, size=14),
                    _build_version_notice(),
                    header_notice,
                    theme_controls,
                    ft.Divider(),
                    cards,
                    ft.Divider(),
                    tables_section,
                ],
                spacing=12,
                scroll=ft.ScrollMode.AUTO,
            ),
            expand=True,
            padding=20,
        )

    def build_query_view():
        database = SQLitePlus(db_path=db_path, cipher_key=cipher_key)
        query_field = ft.TextField(
            label="Consulta SQL",
            hint_text="Escribe una sentencia SELECT o manipulación de datos",
            multiline=True,
            autofocus=True,
            min_lines=3,
            max_lines=6,
            expand=True,
        )
        status_text = ft.Text("", size=14)
        progress_bar = ft.ProgressBar(width=400, visible=False)

        result_table = SmartTable(
            columns=[],
            rows=[],
            page_size=20,
            virtualized=False,
            total_rows=0,
            data_provider=None,
            style=Style(
                bgcolor=ft.Colors.SURFACE,
                border_radius=14,
                padding=ft.Padding(12, 14, 12, 16),
                shadow=ft.BoxShadow(
                    spread_radius=0,
                    blur_radius=18,
                    color=ft.Colors.with_opacity(0.14, ft.Colors.BLACK),
                ),
            ),
        )

        result_container = result_table.build()
        data_table = result_container.controls[0]

        presets = {
            "Listar tablas": "SELECT name, type FROM sqlite_master WHERE type IN ('table','view') ORDER BY name",
            "Últimos registros del log": "SELECT action, timestamp FROM logs ORDER BY timestamp DESC LIMIT 50",
        }

        preset_dropdown = ft.Dropdown(
            label="Plantillas rápidas",
            options=[ft.dropdown.Option(key) for key in presets],
            on_change=lambda e: _apply_preset(e, query_field, presets),
            width=350,
        )

        def _create_data_row(record: tuple[object, ...]) -> ft.DataRow:
            return ft.DataRow(
                cells=[ft.DataCell(ft.Text("NULL" if value is None else str(value))) for value in record]
            )

        def run_query(event):
            sql = (query_field.value or "").strip()
            if not sql:
                status_text.value = "Escribe una consulta para ejecutarla."
                status_text.color = ft.Colors.AMBER
                status_text.update()
                return

            keyword = sql.split(maxsplit=1)[0].lower()
            progress_bar.visible = True
            event.page.update()

            try:
                if keyword in {"select", "pragma", "with"}:
                    columns, limited_rows, truncated = _fetch_rows_respecting_limit(
                        database, sql, max_rows
                    )
                    resolved_columns = [
                        column or f"columna {index + 1}"
                        for index, column in enumerate(columns or [])
                    ]
                    if not resolved_columns:
                        first_row_length = len(limited_rows[0]) if limited_rows else 0
                        resolved_columns = [f"columna {index + 1}" for index in range(first_row_length)]

                    resolved_page_size = min(max_rows, 20)
                    result_table.columns = resolved_columns
                    data_table.columns = [ft.DataColumn(ft.Text(name)) for name in resolved_columns]
                    result_table.page_size = resolved_page_size
                    result_table.total_rows = len(limited_rows)

                    result_rows = [tuple(row) for row in limited_rows]
                    result_table.virtualized = len(result_rows) > resolved_page_size
                    if result_table.virtualized:
                        result_table.data_provider = (
                            lambda start, end: [_create_data_row(record) for record in result_rows[start:end]]
                        )
                        data_table.rows = result_table._get_page_rows()
                    else:
                        result_table.rows = [_create_data_row(record) for record in result_rows]
                        result_table.data_provider = None
                        data_table.rows = result_table._get_page_rows()
                    if truncated:
                        status_text.value = (
                            f"Se muestran {len(limited_rows)} fila(s) (límite configurado: {max_rows}). "
                            "Añade LIMIT a la consulta para obtener más resultados."
                        )
                    else:
                        status_text.value = f"La consulta devolvió {len(limited_rows)} fila(s)."
                    status_text.color = ft.Colors.GREEN
                elif read_only:
                    status_text.value = "La interfaz está en modo solo lectura. Usa --allow-write para habilitar cambios."
                    status_text.color = ft.Colors.RED
                    result_table.rows = []
                    result_table.columns = []
                    result_table.total_rows = 0
                    result_table.data_provider = None
                    result_table.virtualized = False
                    data_table.columns = []
                    data_table.rows = []
                else:
                    last_id = database.execute_query(sql)
                    result_table.rows = []
                    result_table.columns = []
                    result_table.total_rows = 0
                    result_table.data_provider = None
                    result_table.virtualized = False
                    data_table.columns = []
                    data_table.rows = []
                    status_text.value = (
                        "Operación de escritura completada." if last_id is None else f"ID afectado: {last_id}"
                    )
                    status_text.color = ft.Colors.GREEN
            except (SQLitePlusQueryError, SQLitePlusCipherError) as exc:
                status_text.value = str(exc)
                status_text.color = ft.Colors.RED
                result_table.rows = []
                result_table.columns = []
                result_table.total_rows = 0
                result_table.data_provider = None
                result_table.virtualized = False
                data_table.columns = []
                data_table.rows = []
            finally:
                progress_bar.visible = False
                event.page.update()

        run_button = ft.FilledButton("Ejecutar", icon=ft.Icons.PLAY_ARROW, on_click=run_query)

        return ft.Container(
            content=ft.Column(
                [
                    ft.Row([query_field], expand=True),
                    ft.Row([preset_dropdown, run_button, progress_bar], alignment=ft.MainAxisAlignment.START, spacing=16),
                    result_container,
                    status_text,
                ],
                expand=True,
                spacing=12,
            ),
            expand=True,
            padding=20,
        )

    def build_log_view():
        database = SQLitePlus(db_path=db_path, cipher_key=cipher_key)
        columns, rows = database.fetch_query_with_columns(
            "SELECT action AS Acción, timestamp AS Momento FROM logs ORDER BY timestamp DESC LIMIT ?",
            params=(max_rows,),
        )

        if not rows:
            empty_state = ft.Column(
                [
                    ft.Icon(ft.Icons.HISTORY, size=48, color=ft.Colors.AMBER),
                    ft.Text("El historial aún no tiene eventos registrados.", size=16),
                ],
                alignment=ft.MainAxisAlignment.CENTER,
                horizontal_alignment=ft.CrossAxisAlignment.CENTER,
                expand=True,
            )
            return ft.Container(content=empty_state, expand=True, padding=20)

        log_table = ft.DataTable(
            columns=[ft.DataColumn(ft.Text(column)) for column in columns],
            rows=[
                ft.DataRow(cells=[ft.DataCell(ft.Text("NULL" if value is None else str(value))) for value in row])
                for row in rows
            ],
            heading_row_color=ft.Colors.SURFACE_VARIANT,
            column_spacing=32,
        )

        return ft.Container(
            content=ft.Column(
                [
                    ft.Text("Historial de eventos", size=22, weight=ft.FontWeight.BOLD),
                    ft.Text("Consulta las últimas acciones registradas por SQLitePlus."),
                    ft.Divider(),
                    log_table,
                ],
                spacing=12,
            ),
            padding=20,
            expand=True,
        )

    def build_accessibility_view():
        nonlocal theme_status_container

        tips = [
            "Pulsa Ctrl+K para abrir rápidamente la paleta de comandos.",
            "Alterna claro/oscuro desde la cabecera para mejorar el contraste en vivo.",
            "Ajusta el tamaño de texto dentro de las tablas interactivas desde el control deslizante.",
            "Personaliza el color de acento desde el selector rápido sin recargar la sesión.",
        ]

        tip_list = ft.ListView(
            controls=[
                ft.ListTile(
                    leading=ft.Icon(ft.Icons.CHECK_CIRCLE_OUTLINE, color=primary_color),
                    title=ft.Text(message, selectable=True),
                )
                for message in tips
            ],
            expand=True,
            spacing=4,
        )

        badges = ft.Wrap(
            [
                ft.Chip(label=ft.Text("Ctrl + K"), avatar=ft.Icon(ft.Icons.KEYBOARD_COMMAND_KEY)),
                ft.Chip(label=ft.Text("Ctrl + Enter"), avatar=ft.Icon(ft.Icons.PLAY_ARROW)),
                ft.Chip(label=ft.Text("Ctrl + S"), avatar=ft.Icon(ft.Icons.SAVE)),
            ],
            spacing=12,
            run_spacing=12,
        )

        theme_status_container = ft.Container(
            content=ft.Row(
                [
                    ft.Icon(ft.Icons.PALETTE_OUTLINED, color=theme_state["accent"]),
                    theme_status_text,
                ],
                spacing=10,
                vertical_alignment=ft.CrossAxisAlignment.CENTER,
            ),
            bgcolor=ft.Colors.with_opacity(0.04, theme_state["accent"]),
            border_radius=12,
            padding=ft.Padding(12, 10, 12, 10),
        )

        info_cards = ft.Column(
            [
                ft.Text("Atajos y ayudas", size=22, weight=ft.FontWeight.BOLD),
                ft.Text(
                    "SQLitePlus Studio integra accesos rápidos y elementos accesibles para acelerar tu trabajo diario.",
                    opacity=0.8,
                ),
                ft.Divider(),
                badges,
                ft.Divider(),
                tip_list,
                theme_status_container,
            ],
            spacing=12,
            expand=True,
        )

        return ft.Container(content=info_cards, padding=24, expand=True)

    routes = {
        "Resumen": build_summary_view,
        "Consultas": build_query_view,
        "Historial": build_log_view,
        "Accesibilidad": build_accessibility_view,
    }

    sidebar_items = [
        {"title": "Resumen", "icon": ft.Icons.DASHBOARD},
        {"title": "Consultas", "icon": ft.Icons.TERMINAL},
        {"title": "Historial", "icon": ft.Icons.HISTORY},
        {"title": "Accesibilidad", "icon": ft.Icons.ACCESSIBILITY_NEW},
    ]

    FletPlusApp.start(
        routes=routes,
        sidebar_items=sidebar_items,
        commands=commands,
        title="SQLitePlus Studio",
        theme_config=theme_config,
    )


cli.add_command(init_db)
cli.add_command(execute)
cli.add_command(fetch)
cli.add_command(export_csv)
cli.add_command(export_query)
cli.add_command(backup)
cli.add_command(list_tables)
cli.add_command(describe_table)
cli.add_command(database_info)
cli.add_command(visual_dashboard)


def main(argv: list[str] | None = None) -> int | None:
    def _invoke_cli() -> int | None:
        try:
            return cli.main(args=argv, standalone_mode=True)
        except SystemExit as exc:  # pragma: no cover - comportamiento estándar de Click
            return exc.code

    return run_with_optional_profiling(
        "cli",
        _invoke_cli,
        default_output=Path(__file__).resolve().parents[1] / "reports" / "profile" / "entrypoints",
    )


if __name__ == "__main__":
    raise SystemExit(main())
