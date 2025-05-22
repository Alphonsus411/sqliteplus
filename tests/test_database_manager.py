import unittest

from sqliteplus.utils.database_manager_sync import DatabaseManager


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

    @classmethod
    def tearDownClass(cls):
        """ Limpieza al finalizar las pruebas """
        cls.manager.close_connections()


if __name__ == "__main__":
    unittest.main()
