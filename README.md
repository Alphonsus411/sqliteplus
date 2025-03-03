# SQLitePlus Enhanced

SQLitePlus Enhanced es una librería optimizada para la gestión avanzada de bases de datos SQLite con autenticación JWT, consultas asincrónicas y documentación automática con FastAPI.

## 🚀 Características
- ✅ **Autenticación JWT** 🔐
- ✅ **Soporte para múltiples bases de datos SQLite** 📂
- ✅ **Consultas asincrónicas con `aiosqlite`** ⚡
- ✅ **API documentada automáticamente con Swagger y Redoc** 📜
- ✅ **Optimización con `lifespan` para gestión de conexiones**

## 📦 Instalación
Instala la librería con pip:
```bash
pip install sqliteplus-enhanced
```

## 🌐 Uso Rápido
### 1️⃣ Iniciar el Servidor API
```bash
uvicorn sqliteplus.server_async:app --reload --host 0.0.0.0 --port 8000
```

### 2️⃣ Generar un Token JWT
```bash
curl -X POST "http://127.0.0.1:8000/token" -d "username=admin&password=admin" -H "Content-Type: application/x-www-form-urlencoded"
```

### 3️⃣ Crear una Tabla
```bash
curl -X POST "http://127.0.0.1:8000/databases/test_db/create_table?table_name=logs" -H "Authorization: Bearer <TOKEN>"
```

### 4️⃣ Insertar Datos
```bash
curl -X POST "http://127.0.0.1:8000/databases/test_db/insert?table_name=logs&data=PrimerRegistro" -H "Authorization: Bearer <TOKEN>"
```

### 5️⃣ Consultar Datos
```bash
curl -X GET "http://127.0.0.1:8000/databases/test_db/fetch?table_name=logs" -H "Authorization: Bearer <TOKEN>"
```

### 6️⃣ Eliminar una Tabla
```bash
curl -X DELETE "http://127.0.0.1:8000/databases/test_db/drop_table?table_name=logs" -H "Authorization: Bearer <TOKEN>"
```

## 📜 Documentación de la API
- **Swagger UI:** [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)
- **Redoc:** [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc)

## 🔗 Contribución
Si quieres colaborar, ¡envía un pull request o reporta problemas en el repositorio! 🚀

## 📄 Licencia
MIT License
