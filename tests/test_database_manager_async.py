import asyncio
import os
import unittest
from pathlib import Path
from unittest import mock

from fastapi import HTTPException

from sqliteplus.core.db import AsyncDatabaseManager



class TestAsyncDatabaseManager(unittest.IsolatedAsyncioTestCase):
    """
    Pruebas unitarias para el gestor de bases de datos SQLite asíncrono.
    """

    async def asyncSetUp(self):
        """ Configuración inicial antes de cada prueba """
        self.key_patch = mock.patch.dict(os.environ, {"SQLITE_DB_KEY": "clave-de-prueba"}, clear=False)
        self.key_patch.start()
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

    async def test_accepts_names_with_db_extension(self):
        """Permite operar con nombres que ya incluyen la extensión .db."""
        db_name_with_ext = "custom_async.db"
        await self.manager.execute_query(
            db_name_with_ext,
            "CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, action TEXT)",
        )

        db_path = (self.manager.base_dir / Path(db_name_with_ext)).resolve()
        self.assertTrue(db_path.exists())

    async def test_concurrent_connection_creation(self):
        """Verifica que múltiples solicitudes concurrentes comparten la misma conexión."""
        manager = AsyncDatabaseManager()
        db_name = "test_db_async_concurrent"

        async def obtain_connection():
            return await manager.get_connection(db_name)

        conn1, conn2 = await asyncio.gather(obtain_connection(), obtain_connection())

        self.assertIs(conn1, conn2)
        self.assertIn(db_name, manager.connections)
        self.assertEqual(len(manager.connections), 1)

        await manager.close_connections()

    async def asyncTearDown(self):
        """ Limpieza después de cada prueba """
        await self.manager.close_connections()
        self.key_patch.stop()
        self.manager = None

    async def test_missing_encryption_key_raises_http_exception(self):
        """Verifica que sin clave se devuelve un error controlado."""
        await self.manager.close_connections()
        with mock.patch.dict(os.environ, {"SQLITE_DB_KEY": ""}, clear=False):
            with self.assertRaises(HTTPException) as exc_info:
                await self.manager.get_connection("test_db_async_missing_key")

        self.assertEqual(exc_info.exception.status_code, 503)
        self.assertIn("clave de cifrado", exc_info.exception.detail)

    async def test_encrypted_database_reopens_with_valid_key(self):
        """Confirma que con clave válida se puede operar sobre la base cifrada."""
        db_name = "test_db_async_encrypted"
        await self.manager.execute_query(db_name,
                                         "CREATE TABLE IF NOT EXISTS secure (id INTEGER PRIMARY KEY, data TEXT)")
        await self.manager.execute_query(db_name, "INSERT INTO secure (data) VALUES (?)", ("seguro",))
        result = await self.manager.fetch_query(db_name, "SELECT COUNT(*) FROM secure")
        self.assertEqual(result[0][0], 1)

        await self.manager.close_connections()

        # Reabrir con la misma clave debe funcionar.
        self.manager = AsyncDatabaseManager(reset_on_init=False)
        result = await self.manager.fetch_query(db_name, "SELECT COUNT(*) FROM secure")
        self.assertEqual(result[0][0], 1)

    async def test_close_connections_resets_initialized_registry(self):
        """Tras cerrar conexiones se debe limpiar el registro de bases inicializadas."""

        manager = AsyncDatabaseManager()
        db_name = "test_db_async_reset_registry"
        await manager.execute_query(
            db_name,
            "CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, action TEXT)",
        )
        await manager.execute_query(
            db_name,
            "INSERT INTO logs (action) VALUES (?)",
            ("persistente",),
        )
        await manager.close_connections()

        new_manager = AsyncDatabaseManager()
        try:
            connection = await new_manager.get_connection(db_name)
            cursor = await connection.execute(
                "SELECT name FROM sqlite_master WHERE name = 'logs'"
            )
            rows = await cursor.fetchall()
            self.assertFalse(
                rows,
                "La tabla 'logs' debería eliminarse cuando se reinicia la base tras cerrar conexiones",
            )
        finally:
            await new_manager.close_connections()


class TestAsyncDatabaseManagerLoopReuse(unittest.TestCase):
    def test_reuse_after_closing_connections_in_new_loop(self):
        manager = AsyncDatabaseManager()
        db_name = "test_db_async_loop_reuse"

        async def use_manager_in_loop():
            await manager.execute_query(
                db_name,
                "CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, action TEXT)",
            )
            await manager.execute_query(
                db_name,
                "INSERT INTO logs (action) VALUES (?)",
                ("loop_reuse",),
            )
            results = await manager.fetch_query(db_name, "SELECT COUNT(*) FROM logs")
            self.assertTrue(results)
            await manager.close_connections()

        asyncio.run(use_manager_in_loop())
        asyncio.run(use_manager_in_loop())

    def test_reuse_without_closing_connections_in_new_loop(self):
        manager = AsyncDatabaseManager()
        db_name = "test_db_async_loop_reuse_no_close"

        async def use_manager_in_loop(action_value):
            await manager.execute_query(
                db_name,
                "CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, action TEXT)",
            )
            await manager.execute_query(
                db_name,
                "INSERT INTO logs (action) VALUES (?)",
                (action_value,),
            )
            results = await manager.fetch_query(db_name, "SELECT COUNT(*) FROM logs")
            self.assertTrue(results)

        asyncio.run(use_manager_in_loop("first_run"))
        try:
            asyncio.run(use_manager_in_loop("second_run"))
        except RuntimeError as exc:  # pragma: no cover - explicit verification
            self.fail(f"Se produjo RuntimeError al reutilizar el gestor en un nuevo bucle: {exc}")


if __name__ == "__main__":
    unittest.main()
