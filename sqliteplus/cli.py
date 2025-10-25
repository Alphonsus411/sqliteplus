from __future__ import annotations

import sqlite3

import click

from .utils.constants import DEFAULT_DB_PATH
from .utils.sqliteplus_sync import (
    SQLitePlus,
    SQLitePlusCipherError,
    SQLitePlusQueryError,
)
from .utils.replication_sync import SQLiteReplication


@click.group()
@click.option(
    "--cipher-key",
    envvar="SQLITE_DB_KEY",
    help="Clave SQLCipher a utilizar al abrir las bases de datos.",
)
@click.pass_context
def cli(ctx, cipher_key):
    """Interfaz de Línea de Comandos para SQLitePlus."""
    ctx.ensure_object(dict)
    ctx.obj["cipher_key"] = cipher_key


@click.command()
@click.pass_context
def init_db(ctx):
    """Inicializa la base de datos SQLitePlus."""
    db = SQLitePlus(cipher_key=ctx.obj.get("cipher_key"))
    db.log_action("Inicialización de la base de datos desde CLI")
    click.echo("Base de datos inicializada correctamente.")


@click.command()
@click.argument("query")
@click.pass_context
def execute(ctx, query):
    """Ejecuta una consulta SQL de escritura."""
    db = SQLitePlus(cipher_key=ctx.obj.get("cipher_key"))
    try:
        result = db.execute_query(query)
    except SQLitePlusQueryError as exc:
        raise click.ClickException(str(exc)) from exc
    except SQLitePlusCipherError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Consulta ejecutada. ID insertado: {result}")


@click.command()
@click.argument("query")
@click.pass_context
def fetch(ctx, query):
    """Ejecuta una consulta SQL de lectura."""
    db = SQLitePlus(cipher_key=ctx.obj.get("cipher_key"))
    try:
        result = db.fetch_query(query)
    except SQLitePlusQueryError as exc:
        raise click.ClickException(str(exc)) from exc
    except SQLitePlusCipherError as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(result)


@click.command()
@click.argument("table_name")
@click.argument("output_file")
@click.option(
    "--db-path",
    default=DEFAULT_DB_PATH,
    show_default=True,
    help="Ruta al archivo de base de datos SQLite.",
)
@click.pass_context
def export_csv(ctx, table_name, output_file, db_path):
    """Exporta una tabla a CSV."""
    replicator = SQLiteReplication(db_path=db_path, cipher_key=ctx.obj.get("cipher_key"))
    try:
        replicator.export_to_csv(table_name, output_file)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="table_name") from exc
    except sqlite3.Error as exc:
        raise click.ClickException(str(exc)) from exc
    except (SQLitePlusCipherError, RuntimeError) as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Tabla {table_name} exportada a {output_file}")


@click.command()
@click.pass_context
def backup(ctx):
    """Crea un respaldo de la base de datos."""
    replicator = SQLiteReplication(
        db_path=DEFAULT_DB_PATH, cipher_key=ctx.obj.get("cipher_key")
    )
    try:
        replicator.backup_database()
    except Exception as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo("Copia de seguridad creada correctamente.")

cli.add_command(init_db)
cli.add_command(execute)
cli.add_command(fetch)
cli.add_command(export_csv)
cli.add_command(backup)

if __name__ == "__main__":
    cli()
