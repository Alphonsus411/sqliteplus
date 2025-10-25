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

import sqlite3

import click
from rich import box
from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

from sqliteplus.utils.constants import DEFAULT_DB_PATH
from sqliteplus.utils.sqliteplus_sync import (
    SQLitePlus,
    SQLitePlusCipherError,
    SQLitePlusQueryError,
)
from sqliteplus.utils.replication_sync import SQLiteReplication


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
    help="Ruta del archivo de base de datos a utilizar en todos los comandos.",
)
@click.pass_context
def cli(ctx, cipher_key, db_path):
    """Herramientas de consola para trabajar con SQLitePlus sin programar."""
    ctx.ensure_object(dict)
    ctx.obj["cipher_key"] = cipher_key
    ctx.obj["db_path"] = db_path
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
@click.argument("query", nargs=-1, required=True)
@click.pass_context
def fetch(ctx, query):
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

    if not result:
        console_obj.print(
            Panel.fit(
                Text("No se encontraron filas.", style="bold yellow"),
                title="Consulta vacía",
                border_style="yellow",
            )
        )
        return

    table = Table(box=box.MINIMAL_DOUBLE_HEAD, title="Resultados", header_style="bold magenta")
    if columns:
        for column in columns:
            table.add_column(column or "columna", overflow="fold")
    else:
        for idx in range(len(result[0])):
            table.add_column(f"columna {idx + 1}", overflow="fold")

    for row in result:
        table.add_row(*("NULL" if value is None else str(value) for value in row))

    console_obj.print(table)
    console_obj.print(f"[green]{len(result)}[/green] fila(s) devueltas.")


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
@click.pass_context
def export_csv(ctx, table_name, output_file, db_path):
    """Exporta una tabla a CSV."""
    resolved_db_path = db_path or ctx.obj.get("db_path")
    replicator = SQLiteReplication(
        db_path=resolved_db_path,
        cipher_key=ctx.obj.get("cipher_key"),
    )
    try:
        replicator.export_to_csv(table_name, output_file)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="table_name") from exc
    except sqlite3.Error as exc:
        raise click.ClickException(str(exc)) from exc
    except (SQLitePlusCipherError, RuntimeError) as exc:
        raise click.ClickException(str(exc)) from exc

    ctx.obj["console"].print(
        Panel.fit(
            Text(f"Tabla {table_name} exportada a {output_file}", style="bold green"),
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
            Text(f"Copia de seguridad creada en {backup_path}.", style="bold green"),
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
@click.pass_context
def list_tables(ctx, include_views):
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

cli.add_command(init_db)
cli.add_command(execute)
cli.add_command(fetch)
cli.add_command(export_csv)
cli.add_command(backup)
cli.add_command(list_tables)
cli.add_command(describe_table)
cli.add_command(database_info)

if __name__ == "__main__":
    cli()
