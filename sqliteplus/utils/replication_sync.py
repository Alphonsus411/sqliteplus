import csv
import os
import shutil
import sqlite3



class SQLiteReplication:
    """
    Módulo para exportación y replicación de bases de datos SQLitePlus.
    """

    def __init__(self, db_path=None, backup_dir="backups"):
        if db_path is None:
            from sqliteplus.utils.constants import DEFAULT_DB_PATH

            db_path = DEFAULT_DB_PATH
        self.db_path = db_path
        self.backup_dir = backup_dir
        os.makedirs(self.backup_dir, exist_ok=True)

    def export_to_csv(self, table_name: str, output_file: str):
        """
        Exporta los datos de una tabla a un archivo CSV.
        """
        if not self._is_valid_table_name(table_name):
            raise ValueError(f"Nombre de tabla inválido: {table_name}")

        query = f"SELECT * FROM {self._escape_identifier(table_name)}"

        try:
            with sqlite3.connect(self.db_path) as conn:
                cursor = conn.cursor()
                cursor.execute(query)
                rows = cursor.fetchall()
                column_names = [desc[0] for desc in cursor.description]

            with open(output_file, "w", encoding="utf-8", newline="") as f:
                writer = csv.writer(f)
                writer.writerow(column_names)
                writer.writerows(rows)

            print(f"Datos exportados correctamente a {output_file}")
        except sqlite3.Error as e:
            raise sqlite3.Error(f"Error al exportar datos: {e}") from e

    def backup_database(self):
        """
        Crea una copia de seguridad de la base de datos.
        """
        backup_file = os.path.join(self.backup_dir, f"backup_{self._get_timestamp()}.db")
        try:
            shutil.copy2(self.db_path, backup_file)
            print(f"Copia de seguridad creada en {backup_file}")
            return backup_file
        except Exception as e:
            raise RuntimeError(
                f"Error al realizar la copia de seguridad: {e}"
            ) from e

    def replicate_database(self, target_db_path: str):
        """
        Replica la base de datos en otra ubicación.
        """
        try:
            shutil.copy2(self.db_path, target_db_path)
            print(f"Base de datos replicada en {target_db_path}")
        except Exception as e:
            raise RuntimeError(f"Error en la replicación: {e}") from e

    def _get_timestamp(self):
        """
        Genera un timestamp para los nombres de archivo.
        """
        import datetime
        return datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

    @staticmethod
    def _is_valid_table_name(table_name: str) -> bool:
        return bool(table_name) and table_name.isidentifier()

    @staticmethod
    def _escape_identifier(identifier: str) -> str:
        return f'"{identifier.replace("\"", "\"\"")}"'


if __name__ == "__main__":
    replicator = SQLiteReplication()
    replicator.backup_database()
    replicator.export_to_csv("logs", "logs_export.csv")
