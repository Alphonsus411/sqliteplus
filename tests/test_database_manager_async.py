import asyncio
import importlib
import os
import unittest
import tempfile
from pathlib import Path
from unittest import mock

import aiosqlite

from fastapi import HTTPException

from sqliteplus.core.db import AsyncDatabaseManager, _INITIALIZED_DATABASES



class TestAsyncDatabaseManager(unittest.IsolatedAsyncioTestCase):
    """
    Pruebas unitarias para el gestor de bases de datos SQLite asíncrono.
    """

    async def asyncSetUp(self):
        """ Configuración inicial antes de cada prueba """
        self.key_patch = mock.patch.dict(os.environ, {"SQLITE_DB_KEY": "clave-de-prueba"}, clear=False)
        self.key_patch.start()
        self.manager = AsyncDatabaseManager(require_encryption=False)
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

    async def test_reuses_existing_uppercase_extension(self):
        """Usa la base existente con extensión .DB sin crear un duplicado."""
        with tempfile.TemporaryDirectory() as tmpdir:
            temp_dir = Path(tmpdir)
            original_path = temp_dir / "MAYUS.DB"
            original_path.touch()

            manager = AsyncDatabaseManager(base_dir=temp_dir, require_encryption=False)
            try:
                await manager.execute_query(
                    "MAYUS.DB",
                    "CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, action TEXT)",
                )
            finally:
                await manager.close_connections()

            self.assertTrue(original_path.exists())
            self.assertFalse((temp_dir / "MAYUS.DB.db").exists())

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

    async def test_lazy_env_reset_removes_existing_database(self):
        """Forzar `PYTEST_CURRENT_TEST` tras la inicialización debe limpiar la base."""
        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("PYTEST_CURRENT_TEST", None)
                manager = AsyncDatabaseManager(
                    base_dir=base_dir,
                    require_encryption=False,
                )

            db_name = "lazy_reset_async"
            conn = await manager.get_connection(db_name)
            await conn.close()
            manager.connections.pop(db_name, None)
            manager._connection_loops.pop(db_name, None)
            manager.locks.pop(db_name, None)

            db_path = (base_dir / f"{db_name}.db").resolve()
            db_path.write_text("contenido_residual", encoding="utf-8")

            original_bytes = db_path.read_bytes()
            self.assertEqual(original_bytes, b"contenido_residual")

            with mock.patch.dict(os.environ, {"PYTEST_CURRENT_TEST": "lazy"}, clear=False):
                new_conn = await manager.get_connection(db_name)

            await new_conn.close()
            manager.connections.pop(db_name, None)

            with db_path.open("rb") as handler:
                header = handler.read(6)

            self.assertEqual(header, b"SQLite")

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


class TestGlobalDBManagerEmptyKey(unittest.IsolatedAsyncioTestCase):
    """Escenarios específicos del gestor global instanciado en el módulo."""

    async def test_db_manager_with_empty_key_raises_http_exception(self):
        """El gestor global debe rechazar claves vacías en cada conexión."""

        import sqliteplus.core.db as db_module

        with mock.patch.dict(os.environ, {"SQLITE_DB_KEY": ""}, clear=True):
            reloaded_module = importlib.reload(db_module)

            with self.assertRaises(HTTPException) as exc_info:
                await reloaded_module.db_manager.get_connection("global_empty_key")

            self.assertEqual(exc_info.exception.status_code, 503)
            await reloaded_module.db_manager.close_connections()

        importlib.reload(db_module)
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
                try:
                    await manager_spaces.get_connection("mocked_db_spaces")
                except HTTPException as exc:
                    self.fail(f"No debería lanzarse HTTPException con clave válida: {exc}")

        key_commands_spaces = [cmd for cmd in commands_with_spaces if cmd.startswith("PRAGMA key")]
        self.assertEqual(len(key_commands_spaces), 1)
        self.assertEqual(
            key_commands_spaces[0],
            "PRAGMA key = '  clave con espacios  ';",
        )
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
        self.assertEqual(len(key_commands_blank), 1)
        self.assertEqual(key_commands_blank[0], "PRAGMA key = '    ';")
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

    async def test_retries_initialization_after_pragma_key_failure(self):
        """Si PRAGMA key falla se debe intentar inicializar de nuevo."""

        await self.manager.close_connections()

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            db_name = "retry_pragma_failure"
            absolute_key = str((base_dir / f"{db_name}.db").resolve())

            first_connection = mock.AsyncMock()
            second_connection = mock.AsyncMock()

            async def first_execute(sql, *_):
                if sql.startswith("PRAGMA key"):
                    raise aiosqlite.OperationalError("cipher failed")
                return mock.AsyncMock()

            async def second_execute(sql, *_):
                return mock.AsyncMock()

            first_connection.execute.side_effect = first_execute
            first_connection.commit = mock.AsyncMock()
            first_connection.close = mock.AsyncMock()

            second_connection.execute.side_effect = second_execute
            second_connection.commit = mock.AsyncMock()
            second_connection.close = mock.AsyncMock()

            connect_mock = mock.AsyncMock(side_effect=[first_connection, second_connection])

            manager = AsyncDatabaseManager(base_dir=base_dir)
            try:
                with mock.patch("sqliteplus.core.db.aiosqlite.connect", new=connect_mock):
                    with self.assertRaises(HTTPException):
                        await manager.get_connection(db_name)

                    self.assertNotIn(absolute_key, _INITIALIZED_DATABASES)
                    first_connection.close.assert_awaited_once()

                    connection = await manager.get_connection(db_name)

                self.assertIs(connection, second_connection)
                self.assertIn(absolute_key, _INITIALIZED_DATABASES)
                self.assertEqual(connect_mock.await_count, 2)
            finally:
                await manager.close_connections()

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


class TestAsyncDatabaseManagerResetSafety(unittest.IsolatedAsyncioTestCase):
    """No-regresión para controles de reset en entornos seguros."""

    async def test_force_reset_ignored_outside_safe_environment(self):
        """`SQLITEPLUS_FORCE_RESET` no debe borrar fuera de entornos permitidos."""

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)

            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("SQLITEPLUS_FORCE_RESET", None)
                os.environ.pop("PYTEST_CURRENT_TEST", None)
                os.environ.pop("SQLITEPLUS_ENV", None)
                os.environ.pop("SQLITE_DB_KEY", None)

                manager = AsyncDatabaseManager(
                    base_dir=base_dir,
                    require_encryption=False,
                    reset_on_init=False,
                )

                try:
                    db_name = "force_reset_blocked"
                    db_path = (base_dir / f"{db_name}.db").resolve()
                    conn = await manager.get_connection(db_name)
                    await conn.execute("CREATE TABLE data (value TEXT)")
                    await conn.execute("INSERT INTO data (value) VALUES ('persistente')")
                    await conn.commit()

                    initial_inode = db_path.stat().st_ino

                    os.environ["SQLITEPLUS_FORCE_RESET"] = "1"
                    with self.assertLogs("sqliteplus.core.db", level="WARNING") as logs:
                        same_conn = await manager.get_connection(db_name)

                    cursor = await same_conn.execute("SELECT COUNT(*) FROM data")
                    rows = await cursor.fetchall()
                    self.assertEqual(rows[0][0], 1)
                    self.assertEqual(initial_inode, db_path.stat().st_ino)
                    self.assertTrue(
                        any("Se ignoró SQLITEPLUS_FORCE_RESET" in message for message in logs.output)
                    )
                finally:
                    os.environ.pop("SQLITEPLUS_FORCE_RESET", None)
                    await manager.close_connections()

    async def test_force_reset_recreates_connection_in_test_mode(self):
        """`SQLITEPLUS_FORCE_RESET` debe reinicializar la base en modo seguro de pruebas."""

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)

            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("SQLITEPLUS_FORCE_RESET", None)
                os.environ.pop("SQLITE_DB_KEY", None)
                os.environ["SQLITEPLUS_ENV"] = "test"
                manager = AsyncDatabaseManager(
                    base_dir=base_dir,
                    require_encryption=False,
                    reset_on_init=False,
                )

                try:
                    db_name = "force_reset_same_loop"
                    db_path = (base_dir / f"{db_name}.db").resolve()
                    conn = await manager.get_connection(db_name)
                    await conn.execute(
                        "CREATE TABLE data (value TEXT)"
                    )
                    await conn.execute(
                        "INSERT INTO data (value) VALUES ('persistente')"
                    )
                    await conn.commit()

                    cursor = await conn.execute(
                        "SELECT COUNT(*) FROM sqlite_master WHERE name = 'data'"
                    )
                    existing_rows = await cursor.fetchall()
                    self.assertEqual(existing_rows[0][0], 1)

                    os.environ["SQLITEPLUS_FORCE_RESET"] = "1"
                    new_conn = await manager.get_connection(db_name)

                    cursor = await new_conn.execute(
                        "SELECT COUNT(*) FROM sqlite_master WHERE name = 'data'"
                    )
                    rows = await cursor.fetchall()
                    self.assertEqual(rows[0][0], 0)

                finally:
                    os.environ.pop("SQLITEPLUS_FORCE_RESET", None)
                    os.environ.pop("SQLITEPLUS_ENV", None)
                    await manager.close_connections()

    async def test_reset_on_init_true_overrides_safe_environment_check(self):
        """`reset_on_init=True` debe resetear incluso sin variables de entorno de test."""

        with tempfile.TemporaryDirectory() as tmpdir:
            base_dir = Path(tmpdir)
            db_name = "manual_reset_override"
            db_path = (base_dir / f"{db_name}.db").resolve()

            with mock.patch.dict(os.environ, {}, clear=False):
                os.environ.pop("PYTEST_CURRENT_TEST", None)
                os.environ.pop("SQLITEPLUS_ENV", None)
                os.environ.pop("SQLITEPLUS_FORCE_RESET", None)
                os.environ.pop("SQLITE_DB_KEY", None)

                db_path.write_text("residuo", encoding="utf-8")

                manager = AsyncDatabaseManager(
                    base_dir=base_dir,
                    require_encryption=False,
                    reset_on_init=True,
                )

                try:
                    await manager.execute_query(
                        db_name,
                        "CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, action TEXT)",
                    )

                    with db_path.open("rb") as handler:
                        header = handler.read(6)

                    self.assertEqual(header, b"SQLite")
                finally:
                    await manager.close_connections()


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
