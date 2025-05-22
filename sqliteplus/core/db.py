import aiosqlite
import asyncio
import os


class AsyncDatabaseManager:
    """
    Gestor de bases de datos SQLite asíncrono con `aiosqlite`.
    Permite manejar múltiples bases de datos en paralelo sin bloqueos.
    """

    def __init__(self, base_dir="databases"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)  # Asegura que el directorio exista
        self.connections = {}  # Diccionario de conexiones a bases de datos
        self.locks = {}  # Diccionario de bloqueos asíncronos

    async def get_connection(self, db_name):
        """
        Obtiene una conexión asíncrona a la base de datos especificada.
        Si la conexión no existe, la crea.
        """
        db_path = os.path.join(self.base_dir, f"{db_name}.db")

        if db_name not in self.connections:
            self.connections[db_name] = await aiosqlite.connect(db_path)
            await self.connections[db_name].execute("PRAGMA journal_mode=WAL;")  # Mejora concurrencia
            await self.connections[db_name].commit()
            self.locks[db_name] = asyncio.Lock()

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
