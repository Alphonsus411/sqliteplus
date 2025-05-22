import unittest
import asyncio
from sqliteplus.core.db import AsyncDatabaseManager



class TestAsyncDatabaseManager(unittest.IsolatedAsyncioTestCase):
    """
    Pruebas unitarias para el gestor de bases de datos SQLite asíncrono.
    """

    async def asyncSetUp(self):
        """ Configuración inicial antes de cada prueba """
        self.manager = AsyncDatabaseManager()
        self.db_name = "test_db_async"
        await self.manager.execute_query(self.db_name,
                                         "CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, action TEXT)")

    async def test_insert_and_fetch(self):
        """ Prueba de inserción y consulta en la base de datos asíncrona """
        action = "Test de inserción async"
        await self.manager.execute_query(self.db_name, "INSERT INTO logs (action) VALUES (?)", (action,))
        result = await self.manager.fetch_query(self.db_name, "SELECT * FROM logs")

        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)
        self.assertEqual(result[-1][1], action)  # Última inserción debe coincidir

    async def test_multiple_databases(self):
        """ Prueba la gestión de múltiples bases de datos asíncronas """
        db2 = "test_db_async_2"
        await self.manager.execute_query(db2, "CREATE TABLE IF NOT EXISTS users (id INTEGER PRIMARY KEY, name TEXT)")
        await self.manager.execute_query(db2, "INSERT INTO users (name) VALUES (?)", ("Alice",))
        result = await self.manager.fetch_query(db2, "SELECT * FROM users")

        self.assertIsInstance(result, list)
        self.assertTrue(len(result) > 0)
        self.assertEqual(result[0][1], "Alice")

    async def asyncTearDown(self):
        """ Limpieza después de cada prueba """
        await self.manager.close_connections()


if __name__ == "__main__":
    unittest.main()
