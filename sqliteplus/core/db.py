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
        inicializarla de nuevo. Por defecto se activa sólo durante la ejecución
        de las pruebas (detectado a través de ``PYTEST_CURRENT_TEST``) para evitar
        que queden datos residuales entre ejecuciones repetidas.
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
            self.require_encryption = bool(os.getenv("SQLITE_DB_KEY", "").strip())
        else:
            self.require_encryption = require_encryption
        if reset_on_init is None:
            self._reset_on_init = bool(os.getenv("PYTEST_CURRENT_TEST"))
        else:
            self._reset_on_init = reset_on_init

        self._register_instance()

    def _normalize_db_name(self, raw_name: str) -> tuple[str, Path]:
        sanitized = raw_name.strip()
        if not sanitized:
            raise ValueError("Nombre de base de datos inválido")

        if any(token in sanitized for token in ("..", "/", "\\")):
            raise ValueError("Nombre de base de datos inválido")

        file_name = sanitized if sanitized.endswith(".db") else f"{sanitized}.db"
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

            if canonical_name in self.connections:
                stored_loop = self._connection_loops.get(canonical_name)
                if stored_loop is not current_loop:
                    await self.connections[canonical_name].close()
                    recreate_connection = True
            else:
                recreate_connection = True

            absolute_key = str(db_path)

            if recreate_connection:
                if absolute_key not in _INITIALIZED_DATABASES:
                    if self._reset_on_init and db_path.exists():
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
                _INITIALIZED_DATABASES.add(absolute_key)
                encryption_key = os.getenv("SQLITE_DB_KEY", "").strip()
                if not encryption_key:
                    if self.require_encryption:
                        logger.error(
                            "No se encontró la clave de cifrado requerida en la variable de entorno 'SQLITE_DB_KEY'."
                        )
                        raise HTTPException(
                            status_code=503,
                            detail="Base de datos no disponible: falta la clave de cifrado requerida",
                        )

                connection = await aiosqlite.connect(str(db_path))
                try:
                    if encryption_key:
                        try:
                            await connection.execute("PRAGMA key = ?", (encryption_key,))
                        except aiosqlite.OperationalError as exc:
                            logger.warning(
                                "No se pudo aplicar PRAGMA key para la base '%s': %s. Se continuará sin cifrado.",
                                canonical_name,
                                exc,
                            )
                        except sqlite3.Error:
                            await connection.close()
                            raise
                    await connection.execute("PRAGMA journal_mode=WAL;")  # Mejora concurrencia
                    await connection.commit()
                except Exception:
                    await connection.close()
                    raise

                self.connections[canonical_name] = connection
                self._connection_loops[canonical_name] = current_loop
                self.locks[canonical_name] = asyncio.Lock()
                self._initialized_keys[canonical_name] = absolute_key
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

    async def fetch_query(self, db_name, query, params=()):
        """
        Ejecuta una consulta de lectura en la base de datos especificada.
        """
        normalized = self._normalize_db_name(db_name)
        conn = await self.get_connection(db_name, _normalized=normalized)
        canonical_name, _ = normalized
        lock = self.locks[canonical_name]

        async with lock:
            cursor = await conn.execute(query, params)
            result = await cursor.fetchall()
            return result

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
