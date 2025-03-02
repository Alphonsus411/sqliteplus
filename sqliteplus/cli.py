import click
from sqliteplus.core import SQLitePlus
from sqliteplus.replication import SQLiteReplication

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
def export_csv(table_name, output_file):
    """Exporta una tabla a CSV."""
    replicator = SQLiteReplication()
    replicator.export_to_csv(table_name, output_file)
    click.echo(f"Tabla {table_name} exportada a {output_file}")

@click.command()
def backup():
    """Crea un respaldo de la base de datos."""
    replicator = SQLiteReplication()
    replicator.backup_database()
    click.echo("Copia de seguridad creada correctamente.")

cli.add_command(init_db)
cli.add_command(execute)
cli.add_command(fetch)
cli.add_command(export_csv)
cli.add_command(backup)

if __name__ == "__main__":
    cli()
