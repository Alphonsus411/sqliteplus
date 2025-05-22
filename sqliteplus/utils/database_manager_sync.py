import sqlite3
import threading
import os


class DatabaseManager:
    """
    Gestor de bases de datos SQLite que maneja múltiples bases en paralelo
    y soporta concurrencia con `threading`.
    """

    def __init__(self, base_dir="databases"):
        self.base_dir = base_dir
        os.makedirs(self.base_dir, exist_ok=True)  # Asegura que el directorio exista
        self.connections = {}  # Diccionario de conexiones a bases de datos
        self.locks = {}  # Bloqueos para manejar concurrencia en cada base de datos

    def get_connection(self, db_name):
        """
        Obtiene una conexión a la base de datos especificada.
        Si la conexión no existe, la crea.
        """
        db_path = os.path.join(self.base_dir, f"{db_name}.db")

        if db_name not in self.connections:
            self.connections[db_name] = sqlite3.connect(db_path, check_same_thread=False)
            self.connections[db_name].execute("PRAGMA journal_mode=WAL;")  # Mejora concurrencia
            self.locks[db_name] = threading.Lock()

        return self.connections[db_name]

    def execute_query(self, db_name, query, params=()):
        """
        Ejecuta una consulta de escritura en la base de datos especificada.
        """
        conn = self.get_connection(db_name)
        lock = self.locks[db_name]

        with lock:
            cursor = conn.cursor()
            try:
                cursor.execute(query, params)
                conn.commit()
                return cursor.lastrowid
            except sqlite3.Error as e:
                print(f"Error en la consulta: {e}")
                return None

    def fetch_query(self, db_name, query, params=()):
        """
        Ejecuta una consulta de lectura en la base de datos especificada.
        """
        conn = self.get_connection(db_name)
        lock = self.locks[db_name]

        with lock:
            cursor = conn.cursor()
            try:
                cursor.execute(query, params)
                return cursor.fetchall()
            except sqlite3.Error as e:
                print(f"Error en la consulta: {e}")
                return None

    def close_connections(self):
        """
        Cierra todas las conexiones abiertas.
        """
        for db_name, conn in self.connections.items():
            conn.close()
        self.connections.clear()
        self.locks.clear()


if __name__ == "__main__":
    manager = DatabaseManager()
    manager.execute_query("test_db", "CREATE TABLE IF NOT EXISTS logs (id INTEGER PRIMARY KEY, action TEXT)")
    manager.execute_query("test_db", "INSERT INTO logs (action) VALUES (?)", ("Test de SQLitePlus",))
    print(manager.fetch_query("test_db", "SELECT * FROM logs"))
