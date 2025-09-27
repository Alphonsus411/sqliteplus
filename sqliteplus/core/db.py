import aiosqlite
import asyncio
from pathlib import Path


class AsyncDatabaseManager:
    """
    Gestor de bases de datos SQLite asíncrono con `aiosqlite`.
    Permite manejar múltiples bases de datos en paralelo sin bloqueos.
    """

    def __init__(self, base_dir="databases"):
        self.base_dir = Path(base_dir).resolve()
        self.base_dir.mkdir(parents=True, exist_ok=True)  # Asegura que el directorio exista
        self.connections = {}  # Diccionario de conexiones a bases de datos
        self.locks = {}  # Diccionario de bloqueos asíncronos
        self._creation_lock = None  # Candado para inicialización perezosa de conexiones
        self._creation_lock_loop = None  # Bucle asociado al candado de creación

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
            if db_name not in self.connections:
                self.connections[db_name] = await aiosqlite.connect(str(db_path))
                await self.connections[db_name].execute("PRAGMA journal_mode=WAL;")  # Mejora concurrencia
                await self.connections[db_name].commit()
            self.locks.setdefault(db_name, asyncio.Lock())

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
        self._creation_lock = None
        self._creation_lock_loop = None

db_manager = AsyncDatabaseManager()

if __name__ == "__main__":
    async def main():
        manager = AsyncDatabaseManager()
        await manager.execute_query("test_db", "CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, action TEXT)")
        await manager.execute_query("test_db", "INSERT INTO logs (action) VALUES (?)", ("Test de SQLitePlus Async",))
        logs = await manager.fetch_query("test_db", "SELECT * FROM logs")
        print(logs)
        await manager.close_connections()


    asyncio.run(main())
