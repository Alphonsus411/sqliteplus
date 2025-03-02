import sqlite3
import threading


class SQLitePlus:
    """
    Manejador de SQLite mejorado con soporte para concurrencia y manejo seguro de consultas.
    """

    def __init__(self, db_path="database.db"):
        self.db_path = db_path
        self.lock = threading.Lock()  # Para manejar concurrencia
        self._initialize_db()

    def _initialize_db(self):
        """
        Inicializa la base de datos creando las tablas necesarias si no existen.
        """
        with self.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS logs (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    action TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
                """
            )
            conn.commit()

    def get_connection(self):
        """
        Obtiene una conexión a la base de datos.
        """
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def execute_query(self, query, params=()):
        """
        Ejecuta una consulta de escritura en la base de datos.
        """
        with self.lock:  # Bloquea la ejecución para evitar conflictos
            with self.get_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(query, params)
                    conn.commit()
                    return cursor.lastrowid
                except sqlite3.Error as e:
                    print(f"Error en la consulta: {e}")
                    return None

    def fetch_query(self, query, params=()):
        """
        Ejecuta una consulta de lectura en la base de datos y devuelve los resultados.
        """
        with self.lock:
            with self.get_connection() as conn:
                cursor = conn.cursor()
                try:
                    cursor.execute(query, params)
                    return cursor.fetchall()
                except sqlite3.Error as e:
                    print(f"Error en la consulta: {e}")
                    return None

    def log_action(self, action):
        """
        Registra una acción en la tabla de logs.
        """
        self.execute_query("INSERT INTO logs (action) VALUES (?)", (action,))


if __name__ == "__main__":
    db = SQLitePlus()
    db.log_action("Inicialización del sistema")
    print("SQLitePlus está listo para usar.")
