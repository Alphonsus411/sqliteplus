import asyncio
import atexit
import logging
import os
import threading
from pathlib import Path
import sqlite3
import weakref

import aiosqlite

from fastapi import HTTPException


logger = logging.getLogger(__name__)


_INITIALIZED_DATABASES: set[str] = set()
_LIVE_MANAGERS = weakref.WeakSet()


def _is_truthy(value: str | None) -> bool:
    if value is None:
        return False
    normalized = value.strip().lower()
    if not normalized:
        return False
    return normalized not in {"0", "false", "no", "off"}


class AsyncDatabaseManager:
    """
    Gestor de bases de datos SQLite asíncrono con `aiosqlite`.
    Permite manejar múltiples bases de datos en paralelo sin bloqueos.

    Parameters
    ----------
    base_dir:
        Directorio donde se almacenarán los archivos de las bases de datos.
    require_encryption:
        Obliga a que exista una clave ``SQLITE_DB_KEY`` en el entorno antes de abrir
        conexiones. Si es ``None`` se detecta automáticamente.
    reset_on_init:
        Cuando es ``True`` se elimina la base de datos existente antes de
        inicializarla de nuevo. Además del valor pasado explícitamente, el
        gestor vuelve a comprobar en cada creación de conexión las variables
        ``PYTEST_CURRENT_TEST`` y ``SQLITEPLUS_FORCE_RESET`` para decidir si debe
        borrar el archivo, evitando residuos incluso si el gestor global ya está
        instanciado.
    """

    def __init__(
        self,
        base_dir="databases",
        require_encryption: bool | None = None,
        reset_on_init: bool | None = None,
    ):
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)  # Asegura que el directorio exista
        self.connections = {}  # Diccionario de conexiones a bases de datos
        self.locks = {}  # Diccionario de bloqueos asíncronos
        self._connection_loops = {}  # Bucle de evento asociado a cada conexión
        self._initialized_keys: dict[str, str] = {}  # Mapea nombres canónicos a rutas absolutas
        self._creation_lock = None  # Candado para inicialización perezosa de conexiones
        self._creation_lock_loop = None  # Bucle asociado al candado de creación
        if require_encryption is None:
            self.require_encryption = os.getenv("SQLITE_DB_KEY") is not None
        else:
            self.require_encryption = require_encryption
        self._auto_reset_detection = reset_on_init is None
        if reset_on_init is None:
            self._reset_on_init = bool(os.getenv("PYTEST_CURRENT_TEST"))
        else:
            self._reset_on_init = reset_on_init

        self._register_instance()

    def _should_reset_database(self) -> bool:
        if self._reset_on_init:
            return True
        if self._auto_reset_detection and os.getenv("PYTEST_CURRENT_TEST"):
            return True
        return _is_truthy(os.getenv("SQLITEPLUS_FORCE_RESET"))

    def _is_force_reset_requested(self) -> bool:
        return _is_truthy(os.getenv("SQLITEPLUS_FORCE_RESET"))

    def _normalize_db_name(self, raw_name: str) -> tuple[str, Path]:
        sanitized = raw_name.strip()
        if not sanitized:
            raise ValueError("Nombre de base de datos inválido")

        if any(token in sanitized for token in ("..", "/", "\\")):
            raise ValueError("Nombre de base de datos inválido")

        file_name = sanitized if sanitized.lower().endswith(".db") else f"{sanitized}.db"
        db_path = (self.base_dir / Path(file_name)).resolve()
        if self.base_dir not in db_path.parents:
            raise ValueError("Nombre de base de datos fuera del directorio permitido")

        return db_path.stem, db_path

    async def get_connection(self, db_name, *, _normalized: tuple[str, Path] | None = None):
        """
        Obtiene una conexión asíncrona a la base de datos especificada.
        Si la conexión no existe, la crea.
        """
        canonical_name, db_path = _normalized or self._normalize_db_name(db_name)

        current_loop = asyncio.get_running_loop()

        if self._creation_lock is None or self._creation_lock_loop is not current_loop:
            self._creation_lock = asyncio.Lock()
            self._creation_lock_loop = current_loop

        async with self._creation_lock:
            recreate_connection = False
            should_reset = self._should_reset_database()
            force_reset = self._is_force_reset_requested()

            if canonical_name in self.connections:
                stored_loop = self._connection_loops.get(canonical_name)
                if stored_loop is not current_loop:
                    await self.connections[canonical_name].close()
                    recreate_connection = True

                    self.connections.pop(canonical_name, None)
                    self.locks.pop(canonical_name, None)
                    self._connection_loops.pop(canonical_name, None)
                    absolute_key_cleanup = self._initialized_keys.pop(canonical_name, None)
                    if absolute_key_cleanup is not None:
                        _INITIALIZED_DATABASES.discard(absolute_key_cleanup)
                elif force_reset:
                    await self.connections[canonical_name].close()
                    recreate_connection = True

                    self.connections.pop(canonical_name, None)
                    self.locks.pop(canonical_name, None)
                    self._connection_loops.pop(canonical_name, None)
                    absolute_key_cleanup = self._initialized_keys.pop(canonical_name, None)
                    if absolute_key_cleanup is not None:
                        _INITIALIZED_DATABASES.discard(absolute_key_cleanup)
            else:
                recreate_connection = True

            absolute_key = str(db_path)

            if recreate_connection:
                # `should_reset` ya se evaluó antes para evitar reusar conexiones obsoletas
                if should_reset:
                    _INITIALIZED_DATABASES.discard(absolute_key)
                if absolute_key not in _INITIALIZED_DATABASES:
                    if should_reset and db_path.exists():
                        try:
                            db_path.unlink()
                        except OSError as exc:
                            logger.warning(
                                "No se pudo eliminar la base '%s' antes de reinicializarla: %s",
                                canonical_name,
                                exc,
                            )
                    wal_shm_paths = [Path(f"{db_path}{suffix}") for suffix in ("-wal", "-shm")]
                    for extra_path in wal_shm_paths:
                        try:
                            extra_path.unlink()
                        except FileNotFoundError:
                            continue
                        except OSError as exc:
                            logger.warning(
                                "No se pudo eliminar el archivo auxiliar '%s' para la base '%s': %s",
                                extra_path,
                                canonical_name,
                                exc,
                            )
                raw_encryption_key = os.getenv("SQLITE_DB_KEY")
                stripped_encryption_key = None
                if raw_encryption_key is not None:
                    stripped_encryption_key = raw_encryption_key.strip()

                if self.require_encryption and (
                    stripped_encryption_key is None or stripped_encryption_key == ""
                ):
                    logger.error(
                        "Clave de cifrado ausente o vacía en la variable de entorno 'SQLITE_DB_KEY'"
                    )
                    raise HTTPException(
                        status_code=503,
                        detail="Base de datos no disponible: falta la clave de cifrado requerida",
                    )

                connection = None
                try:
                    connection = await aiosqlite.connect(str(db_path))
                    if raw_encryption_key is not None:
                        escaped_key = raw_encryption_key.replace("'", "''")
                        try:
                            await connection.execute(f"PRAGMA key = '{escaped_key}';")
                        except (aiosqlite.OperationalError, sqlite3.DatabaseError) as exc:
                            logger.error(
                                "Error al aplicar PRAGMA key para la base '%s': %s.",
                                canonical_name,
                                exc,
                            )
                            raise HTTPException(
                                status_code=503,
                                detail="Base de datos no disponible: fallo al aplicar la clave de cifrado",
                            ) from exc
                    await connection.execute("PRAGMA journal_mode=WAL;")  # Mejora concurrencia
                    await connection.commit()
                except Exception:
                    if connection is not None:
                        await connection.close()
                    _INITIALIZED_DATABASES.discard(absolute_key)
                    raise

                self.connections[canonical_name] = connection
                self._connection_loops[canonical_name] = current_loop
                self.locks[canonical_name] = asyncio.Lock()
                self._initialized_keys[canonical_name] = absolute_key
                _INITIALIZED_DATABASES.add(absolute_key)
            else:
                self.locks.setdefault(canonical_name, asyncio.Lock())
                self._connection_loops.setdefault(canonical_name, current_loop)
                self._initialized_keys.setdefault(canonical_name, absolute_key)

        return self.connections[canonical_name]

    async def execute_query(self, db_name, query, params=()):
        """
        Ejecuta una consulta de escritura en la base de datos especificada.
        """
        normalized = self._normalize_db_name(db_name)
        conn = await self.get_connection(db_name, _normalized=normalized)
        canonical_name, _ = normalized
        lock = self.locks[canonical_name]

        async with lock:
            cursor = await conn.execute(query, params)
            await conn.commit()
            return cursor.lastrowid

    async def fetch_query_with_columns(self, db_name, query, params=()):
        """Ejecuta una consulta de lectura y retorna también los nombres de columna."""

        normalized = self._normalize_db_name(db_name)
        conn = await self.get_connection(db_name, _normalized=normalized)
        canonical_name, _ = normalized
        lock = self.locks[canonical_name]

        async with lock:
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            column_names = [column[0] for column in cursor.description or []]
            return column_names, rows

    async def fetch_query(self, db_name, query, params=()):
        """
        Ejecuta una consulta de lectura en la base de datos especificada.
        """

        _, rows = await self.fetch_query_with_columns(db_name, query, params)
        return rows

    async def close_connections(self):
        """
        Cierra todas las conexiones abiertas de forma asíncrona y limpia el registro
        de bases inicializadas, de modo que en la siguiente apertura se puedan
        reinicializar si ``reset_on_init`` está activo.
        """
        closed_names = list(self.connections.keys())
        for db_name in closed_names:
            await self.connections[db_name].close()

        self.connections.clear()
        self.locks.clear()
        self._connection_loops.clear()
        self._creation_lock = None

        for name in closed_names:
            absolute_key = self._initialized_keys.pop(name, None)
            if absolute_key is not None:
                _INITIALIZED_DATABASES.discard(absolute_key)

        self._initialized_keys.clear()

    # -- Gestión de ciclo de vida -------------------------------------------------

    _shutdown_hook_registered = False

    def _register_instance(self) -> None:
        _LIVE_MANAGERS.add(self)

        if not AsyncDatabaseManager._shutdown_hook_registered:
            atexit.register(self._cleanup_open_managers)
            AsyncDatabaseManager._shutdown_hook_registered = True

    @staticmethod
    def _cleanup_open_managers() -> None:
        managers = list(_LIVE_MANAGERS)
        for manager in managers:
            if not manager.connections:
                continue
            try:
                loop = asyncio.new_event_loop()
                try:
                    loop.run_until_complete(manager.close_connections())
                finally:
                    loop.close()
            except Exception:  # pragma: no cover - evita bloquear la salida
                logger.exception("No se pudieron cerrar conexiones SQLite al finalizar las pruebas")

    @staticmethod
    def _close_in_thread(manager_ref: "weakref.ReferenceType[AsyncDatabaseManager]") -> None:
        manager = manager_ref()
        if manager is None:
            return
        try:
            asyncio.run(manager.close_connections())
        except Exception:
            logger.exception("Fallo al liberar conexiones SQLite durante la recolección")

    def __del__(self):  # pragma: no cover - se ejecuta durante la recolección
        connections = getattr(self, "connections", None)
        if connections is None or not connections:
            return

        try:
            loop = asyncio.get_running_loop()
        except RuntimeError:
            loop = None

        if loop and loop.is_running():
            threading.Thread(
                target=self._close_in_thread,
                args=(weakref.ref(self),),
                daemon=True,
            ).start()
            return

        try:
            new_loop = asyncio.new_event_loop()
            try:
                new_loop.run_until_complete(self.close_connections())
            finally:
                new_loop.close()
        except Exception:
            logger.exception("Fallo al liberar conexiones SQLite durante la recolección")

db_manager = AsyncDatabaseManager(require_encryption=False)

if __name__ == "__main__":
    async def main():
        manager = AsyncDatabaseManager()
        await manager.execute_query("test_db", "CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, action TEXT)")
        await manager.execute_query("test_db", "INSERT INTO logs (action) VALUES (?)", ("Test de SQLitePlus Async",))
        logs = await manager.fetch_query("test_db", "SELECT * FROM logs")
        print(logs)
        await manager.close_connections()


    asyncio.run(main())
