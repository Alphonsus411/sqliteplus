import asyncio
import logging
import os
from pathlib import Path
import sqlite3

import aiosqlite

from fastapi import HTTPException


logger = logging.getLogger(__name__)


_INITIALIZED_DATABASES: set[str] = set()


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

    async def get_connection(self, db_name):
        """
        Obtiene una conexión asíncrona a la base de datos especificada.
        Si la conexión no existe, la crea.
        """
        if any(token in db_name for token in ("..", "/", "\\")):
            raise ValueError("Nombre de base de datos inválido")

        db_path = (self.base_dir / Path(f"{db_name}.db")).resolve()
        if self.base_dir not in db_path.parents:
            raise ValueError("Nombre de base de datos fuera del directorio permitido")

        current_loop = asyncio.get_running_loop()

        if self._creation_lock is None or self._creation_lock_loop is not current_loop:
            self._creation_lock = asyncio.Lock()
            self._creation_lock_loop = current_loop

        async with self._creation_lock:
            recreate_connection = False

            if db_name in self.connections:
                stored_loop = self._connection_loops.get(db_name)
                if stored_loop is not current_loop:
                    await self.connections[db_name].close()
                    recreate_connection = True
            else:
                recreate_connection = True

            if recreate_connection:
                if db_name not in _INITIALIZED_DATABASES:
                    if self._reset_on_init and db_path.exists():
                        try:
                            db_path.unlink()
                        except OSError as exc:
                            logger.warning(
                                "No se pudo eliminar la base '%s' antes de reinicializarla: %s",
                                db_name,
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
                                db_name,
                                exc,
                            )
                _INITIALIZED_DATABASES.add(db_name)
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
                                db_name,
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

                self.connections[db_name] = connection
                self._connection_loops[db_name] = current_loop
                self.locks[db_name] = asyncio.Lock()
            else:
                self.locks.setdefault(db_name, asyncio.Lock())
                self._connection_loops.setdefault(db_name, current_loop)

        return self.connections[db_name]

    async def execute_query(self, db_name, query, params=()):
        """
        Ejecuta una consulta de escritura en la base de datos especificada.
        """
        conn = await self.get_connection(db_name)
        lock = self.locks[db_name]

        async with lock:
            cursor = await conn.execute(query, params)
            await conn.commit()
            return cursor.lastrowid

    async def fetch_query(self, db_name, query, params=()):
        """
        Ejecuta una consulta de lectura en la base de datos especificada.
        """
        conn = await self.get_connection(db_name)
        lock = self.locks[db_name]

        async with lock:
            cursor = await conn.execute(query, params)
            result = await cursor.fetchall()
            return result

    async def close_connections(self):
        """
        Cierra todas las conexiones abiertas de forma asíncrona.
        """
        for db_name, conn in self.connections.items():
            await conn.close()
        self.connections.clear()
        self.locks.clear()
        self._connection_loops.clear()
        self._creation_lock = None
        self._creation_lock_loop = None

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
