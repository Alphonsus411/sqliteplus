import io
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path

from sqliteplus.utils.database_manager_sync import DatabaseManager, DatabaseQueryError


class TestDatabaseManager(unittest.TestCase):
    """
    Pruebas unitarias para el gestor de bases de datos SQLite.
    """

    @classmethod
    def setUpClass(cls):
        """ Configuración inicial para las pruebas """
        cls.manager = DatabaseManager()
        cls.db_name = "test_db"
        cls.manager.execute_query(cls.db_name, "CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, action TEXT)")

    def test_insert_and_fetch(self):
        """ Prueba de inserción y consulta en la base de datos """
        action = "Test de inserción"
        self.manager.execute_query(self.db_name, "INSERT INTO logs (action) VALUES (?)", (action,))
        result = self.manager.fetch_query(self.db_name, "SELECT * FROM logs")

        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)
        self.assertEqual(result[-1][1], action)  # Última inserción debe coincidir

    def test_multiple_databases(self):
        """ Prueba la gestión de múltiples bases de datos """
        db2 = "test_db_2"
        self.manager.execute_query(db2, "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)")
        self.manager.execute_query(db2, "INSERT INTO users (name) VALUES (?)", ("Alice",))
        result = self.manager.fetch_query(db2, "SELECT * FROM users")

        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)
        self.assertEqual(result[0][1], "Alice")

    def test_accepts_names_with_db_extension(self):
        """Permite gestionar nombres que ya incluyen la extensión .db."""
        db_name_with_ext = "custom_sync.db"
        self.manager.execute_query(
            db_name_with_ext,
            "CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, action TEXT)",
        )

        db_path = (self.manager.base_dir / Path(db_name_with_ext)).resolve()
        self.assertTrue(db_path.exists())

    def test_reuses_existing_uppercase_extension(self):
        """Usa el archivo existente con extensión .DB sin duplicarla."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_dir = Path(tmpdir)
            original_path = temp_dir / "MAYUS.DB"
            original_path.touch()

            manager = DatabaseManager(base_dir=temp_dir)
            try:
                manager.execute_query(
                    "MAYUS.DB",
                    "CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, action TEXT)",
                )
            finally:
                manager.close_connections()

            self.assertTrue(original_path.exists())
            self.assertFalse((temp_dir / "MAYUS.DB.db").exists())

    def test_invalid_query_raises_and_no_stdout_noise(self):
        """Las consultas inválidas deben lanzar excepción sin escribir en stdout."""
        capture = io.StringIO()
        invalid_query = "INSRT INTO logs (action) VALUES (?)"

        with redirect_stdout(capture):
            with self.assertRaises(DatabaseQueryError):
                self.manager.execute_query(self.db_name, invalid_query, ("Test",))

        self.assertEqual(capture.getvalue(), "")

    @classmethod
    def tearDownClass(cls):
        """ Limpieza al finalizar las pruebas """
        cls.manager.close_connections()


if __name__ == "__main__":
    unittest.main()
