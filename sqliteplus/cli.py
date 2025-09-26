import sqlite3

import click
from sqliteplus.utils.constants import DEFAULT_DB_PATH
from sqliteplus.utils.sqliteplus_sync import SQLitePlus
from sqliteplus.utils.replication_sync import SQLiteReplication


@click.group()
def cli():
    """Interfaz de Línea de Comandos para SQLitePlus."""
    pass

@click.command()
def init_db():
    """Inicializa la base de datos SQLitePlus."""
    db = SQLitePlus()
    db.log_action("Inicialización de la base de datos desde CLI")
    click.echo("Base de datos inicializada correctamente.")

@click.command()
@click.argument("query")
def execute(query):
    """Ejecuta una consulta SQL de escritura."""
    db = SQLitePlus()
    result = db.execute_query(query)
    click.echo(f"Consulta ejecutada. ID insertado: {result}")

@click.command()
@click.argument("query")
def fetch(query):
    """Ejecuta una consulta SQL de lectura."""
    db = SQLitePlus()
    result = db.fetch_query(query)
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
def export_csv(table_name, output_file, db_path):
    """Exporta una tabla a CSV."""
    replicator = SQLiteReplication(db_path=db_path)
    try:
        replicator.export_to_csv(table_name, output_file)
    except ValueError as exc:
        raise click.BadParameter(str(exc), param_hint="table_name") from exc
    except sqlite3.Error as exc:
        raise click.ClickException(str(exc)) from exc

    click.echo(f"Tabla {table_name} exportada a {output_file}")

@click.command()
def backup():
    """Crea un respaldo de la base de datos."""
    replicator = SQLiteReplication(db_path=DEFAULT_DB_PATH)
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
