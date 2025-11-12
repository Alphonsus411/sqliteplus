import asyncio
import os
import unittest
import tempfile
from pathlib import Path
from unittest import mock

import aiosqlite

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
        with mock.patch.dict(os.environ, {}, clear=False):
            os.environ.pop("SQLITE_DB_KEY", None)
            with self.assertRaises(HTTPException) as exc_info:
                await self.manager.get_connection("test_db_async_missing_key")

        self.assertEqual(exc_info.exception.status_code, 503)
        self.assertIn("clave de cifrado", exc_info.exception.detail)

    async def test_applies_encryption_key_literal_and_raises_on_failure(self):
        """Simula `aiosqlite` para validar el PRAGMA key y su manejo de errores."""

        await self.manager.close_connections()

        commands: list[str] = []

        async def fake_execute(sql, *_):
            commands.append(sql)
            return mock.AsyncMock()

        fake_connection = mock.AsyncMock()
        fake_connection.execute.side_effect = fake_execute
        fake_connection.commit = mock.AsyncMock()
        fake_connection.close = mock.AsyncMock()

        async def failing_execute(sql, *_):
            if sql.startswith("PRAGMA key"):
                raise aiosqlite.OperationalError("cipher failure")
            return mock.AsyncMock()

        with mock.patch("sqliteplus.core.db.aiosqlite.connect", new=mock.AsyncMock(return_value=fake_connection)):
            with mock.patch.dict(os.environ, {"SQLITE_DB_KEY": "clave'con"}, clear=False):
                manager = AsyncDatabaseManager()
                await manager.get_connection("mocked_db")

        key_commands = [cmd for cmd in commands if cmd.startswith("PRAGMA key")]
        self.assertEqual(len(key_commands), 1)
        self.assertIn("'clave''con'", key_commands[0])
        self.assertFalse(fake_connection.close.await_args_list)

        await manager.close_connections()

        commands_with_spaces: list[str] = []

        async def fake_execute_spaces(sql, *_):
            commands_with_spaces.append(sql)
            return mock.AsyncMock()

        connection_with_spaces = mock.AsyncMock()
        connection_with_spaces.execute.side_effect = fake_execute_spaces
        connection_with_spaces.commit = mock.AsyncMock()
        connection_with_spaces.close = mock.AsyncMock()

        with mock.patch(
            "sqliteplus.core.db.aiosqlite.connect",
            new=mock.AsyncMock(return_value=connection_with_spaces),
        ):
            key_with_spaces = "  clave con espacios  "
            with mock.patch.dict(os.environ, {"SQLITE_DB_KEY": key_with_spaces}, clear=False):
                manager_spaces = AsyncDatabaseManager()
                await manager_spaces.get_connection("mocked_db_spaces")

        key_commands_spaces = [cmd for cmd in commands_with_spaces if cmd.startswith("PRAGMA key")]
        self.assertEqual(len(key_commands_spaces), 1)
        self.assertEqual(key_commands_spaces[0], "PRAGMA key = 'clave con espacios';")
        self.assertFalse(connection_with_spaces.close.await_args_list)

        await manager_spaces.close_connections()

        commands_blank: list[str] = []

        async def fake_execute_blank(sql, *_):
            commands_blank.append(sql)
            return mock.AsyncMock()

        connection_blank = mock.AsyncMock()
        connection_blank.execute.side_effect = fake_execute_blank
        connection_blank.commit = mock.AsyncMock()
        connection_blank.close = mock.AsyncMock()

        with mock.patch(
            "sqliteplus.core.db.aiosqlite.connect",
            new=mock.AsyncMock(return_value=connection_blank),
        ):
            with mock.patch.dict(os.environ, {"SQLITE_DB_KEY": "    "}, clear=False):
                manager_blank = AsyncDatabaseManager(require_encryption=False)
                await manager_blank.get_connection("mocked_db_blank")

        key_commands_blank = [cmd for cmd in commands_blank if cmd.startswith("PRAGMA key")]
        self.assertFalse(
            key_commands_blank,
            "No se debe ejecutar PRAGMA key cuando la clave opcional queda vacía tras normalizarla.",
        )
        self.assertFalse(connection_blank.close.await_args_list)

        await manager_blank.close_connections()

        failing_connection = mock.AsyncMock()
        failing_connection.execute.side_effect = failing_execute
        failing_connection.commit = mock.AsyncMock()
        failing_connection.close = mock.AsyncMock()

        with mock.patch("sqliteplus.core.db.aiosqlite.connect", new=mock.AsyncMock(return_value=failing_connection)):
            with mock.patch.dict(os.environ, {"SQLITE_DB_KEY": "clave"}, clear=False):
                manager = AsyncDatabaseManager()
                with self.assertRaises(HTTPException) as exc_info:
                    await manager.get_connection("failing_db")

        self.assertEqual(exc_info.exception.status_code, 503)
        failing_connection.close.assert_awaited_once()
        self.assertNotIn("failing_db", manager.connections)

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

    async def test_blank_encryption_key_raises_when_required(self):
        """Una clave vacía debe rechazarse si el cifrado es obligatorio."""

        await self.manager.close_connections()

        with mock.patch.dict(os.environ, {"SQLITE_DB_KEY": "   "}, clear=False):
            manager = AsyncDatabaseManager(require_encryption=True)
            with self.assertRaises(HTTPException) as exc_info:
                await manager.get_connection("db_blank_required")

        self.assertEqual(exc_info.exception.status_code, 503)

    async def test_reset_on_init_isolated_by_base_dir(self):
        """Cada gestor elimina su propia base aunque compartan nombre canónico."""

        db_name = "shared_name"

        with tempfile.TemporaryDirectory() as dir_one, tempfile.TemporaryDirectory() as dir_two:
            base_one = Path(dir_one)
            base_two = Path(dir_two)
            db_one = base_one / f"{db_name}.db"
            db_two = base_two / f"{db_name}.db"

            marker_one = b"primera"
            marker_two = b"segunda"
            db_one.write_bytes(marker_one)
            db_two.write_bytes(marker_two)

            manager_one = AsyncDatabaseManager(base_dir=base_one, reset_on_init=True)
            manager_two = AsyncDatabaseManager(base_dir=base_two, reset_on_init=True)

            try:
                await manager_one.execute_query(
                    db_name,
                    "CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, action TEXT)",
                )

                header_one = db_one.read_bytes()[:15]
                self.assertTrue(
                    header_one.startswith(b"SQLite format 3"),
                    "La base del primer gestor debería haberse reinicializado.",
                )

                self.assertEqual(
                    db_two.read_bytes(),
                    marker_two,
                    "La base del segundo gestor no debe modificarse todavía.",
                )

                await manager_one.close_connections()

                await manager_two.execute_query(
                    db_name,
                    "CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, action TEXT)",
                )

                header_two = db_two.read_bytes()[:15]
                self.assertTrue(
                    header_two.startswith(b"SQLite format 3"),
                    "La base del segundo gestor debería haberse reinicializado al abrirse.",
                )
            finally:
                await manager_one.close_connections()
                await manager_two.close_connections()


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
