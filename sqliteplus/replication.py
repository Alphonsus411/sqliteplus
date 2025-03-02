import sqlite3
import os
import shutil
from sqliteplus.core import SQLitePlus


class SQLiteReplication:
    """
    Módulo para exportación y replicación de bases de datos SQLitePlus.
    """

    def __init__(self, db_path="database.db", backup_dir="backups"):
        self.db_path = db_path
        self.backup_dir = backup_dir
        os.makedirs(self.backup_dir, exist_ok=True)

    def export_to_csv(self, table_name: str, output_file: str):
        """
        Exporta los datos de una tabla a un archivo CSV.
        """
        conn = SQLitePlus().get_connection()
        cursor = conn.cursor()

        try:
            cursor.execute(f"SELECT * FROM {table_name}")
            rows = cursor.fetchall()
            column_names = [desc[0] for desc in cursor.description]

            with open(output_file, "w", encoding="utf-8") as f:
                f.write(",".join(column_names) + "\n")
                for row in rows:
                    f.write(",".join(map(str, row)) + "\n")

            print(f"Datos exportados correctamente a {output_file}")
        except sqlite3.Error as e:
            print(f"Error al exportar datos: {e}")
        finally:
            conn.close()

    def backup_database(self):
        """
        Crea una copia de seguridad de la base de datos.
        """
        backup_file = os.path.join(self.backup_dir, f"backup_{self._get_timestamp()}.db")
        try:
            shutil.copy2(self.db_path, backup_file)
            print(f"Copia de seguridad creada en {backup_file}")
        except Exception as e:
            print(f"Error al realizar la copia de seguridad: {e}")

    def replicate_database(self, target_db_path: str):
        """
        Replica la base de datos en otra ubicación.
        """
        try:
            shutil.copy2(self.db_path, target_db_path)
            print(f"Base de datos replicada en {target_db_path}")
        except Exception as e:
            print(f"Error en la replicación: {e}")

    def _get_timestamp(self):
        """
        Genera un timestamp para los nombres de archivo.
        """
        import datetime
        return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")


if __name__ == "__main__":
    replicator = SQLiteReplication()
    replicator.backup_database()
    replicator.export_to_csv("logs", "logs_export.csv")
