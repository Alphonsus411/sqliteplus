import aiosqlite
import asyncio
import os

class AsyncSQLitePlus:
    """
    Manejador de SQLite asincrónico con soporte para concurrencia y registro de logs.
    """

    def __init__(self, db_path="sqliteplus/databases/database.db"):
        self.db_path = db_path
        self.lock = asyncio.Lock()
        self.initialized = False

    async def initialize(self):
        if self.initialized:
            return
        async with self.lock:
            async with aiosqlite.connect(self.db_path) as conn:
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS logs (
                        id INTEGER PRIMARY KEY AUTOINCREMENT,
                        action TEXT,
                        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                    )
                """)
                await conn.commit()
            self.initialized = True

    async def execute_query(self, query, params=()):
        async with self.lock:
            async with aiosqlite.connect(self.db_path) as conn:
                try:
                    cursor = await conn.execute(query, params)
                    await conn.commit()
                    return cursor.lastrowid
                except aiosqlite.Error as e:
                    print(f"Error en la consulta: {e}")
                    return None

    async def fetch_query(self, query, params=()):
        async with self.lock:
            async with aiosqlite.connect(self.db_path) as conn:
                try:
                    cursor = await conn.execute(query, params)
                    return await cursor.fetchall()
                except aiosqlite.Error as e:
                    print(f"Error en la consulta: {e}")
                    return None

    async def log_action(self, action):
        await self.initialize()
        await self.execute_query("INSERT INTO logs (action) VALUES (?)", (action,))
