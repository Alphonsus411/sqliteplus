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

from sqliteplus.utils.constants import DEFAULT_DB_PATH
from sqliteplus.utils.sqliteplus_sync import (
    SQLitePlus,
    SQLitePlusCipherError,
    SQLitePlusQueryError,
)
from sqliteplus.utils.replication_sync import SQLiteReplication


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


@click.command(help="Crea la base de datos si no existe y registra la acción en el historial.")
@click.pass_context
def init_db(ctx):
    """Inicializa la base de datos SQLitePlus."""
    db = SQLitePlus(
        db_path=ctx.obj.get("db_path"),
        cipher_key=ctx.obj.get("cipher_key"),
    )
    db.log_action("Inicialización de la base de datos desde CLI")
    click.echo(f"Base de datos preparada en {db.db_path}.")


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

    click.echo("Consulta ejecutada correctamente.")
    if result is not None:
        click.echo(f"ID insertado: {result}")


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
        result = db.fetch_query(sql)
    except SQLitePlusQueryError as exc:
        raise click.ClickException(str(exc)) from exc
    except SQLitePlusCipherError as exc:
        raise click.ClickException(str(exc)) from exc

    if not result:
        click.echo("No se encontraron filas.")
        return

    click.echo("Resultados:")
    for row in result:
        click.echo(" | ".join(str(value) for value in row))


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

    click.echo(f"Tabla {table_name} exportada a {output_file}")


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

    click.echo(f"Copia de seguridad creada en {backup_path}.")

cli.add_command(init_db)
cli.add_command(execute)
cli.add_command(fetch)
cli.add_command(export_csv)
cli.add_command(backup)

if __name__ == "__main__":
    cli()
