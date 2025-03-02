# 📌 SQLitePlus - Base de Datos Mejorada con Cifrado y Caché 🚀

## 📖 Descripción
SQLitePlus es una implementación mejorada de SQLite con soporte para:
- **Cifrado de base de datos con SQLCipher** 🔒
- **Caché en Redis** para mejorar el rendimiento ⚡
- **Manejo de concurrencia con threading** 🛠️
- **Exportación y replicación de datos** 📂
- **Interfaz CLI para administración desde la terminal** 🖥️
- **Servidor API con FastAPI** para integración flexible 🌐

---

## 📦 Instalación
### **1️⃣ Clonar el Repositorio**
```bash
git clone https://github.com/tuusuario/sqliteplus.git
cd sqliteplus
```

### **2️⃣ Crear un Entorno Virtual**
```bash
python -m venv .venv
source .venv/bin/activate  # En Linux/Mac
.venv\Scripts\activate     # En Windows
```

### **3️⃣ Instalar Dependencias**
```bash
pip install -r requirements.txt
```

---

## 🚀 Uso

### **🔹 Inicializar la Base de Datos**
```bash
python -m sqliteplus.cli init-db
```

### **🔹 Ejecutar una Consulta de Escritura**
```bash
python -m sqliteplus.cli execute "INSERT INTO logs (action) VALUES ('Test desde CLI')"
```

### **🔹 Ejecutar una Consulta de Lectura**
```bash
python -m sqliteplus.cli fetch "SELECT * FROM logs"
```

### **🔹 Crear una Copia de Seguridad**
```bash
python -m sqliteplus.cli backup
```

### **🔹 Exportar una Tabla a CSV**
```bash
python -m sqliteplus.cli export-csv logs logs_export.csv
```

---

## ⚙️ Configuración de Redis (Opcional pero Recomendado)
Si deseas habilitar la caché en Redis:
1. **Iniciar Redis en Local**
   ```bash
   redis-server
   ```
2. **Verificar que Redis está activo**
   ```bash
   redis-cli ping  # Debería responder con 'PONG'
   ```

---

## 📡 Uso del Servidor API
### **🔹 Iniciar el Servidor FastAPI**
```bash
uvicorn sqliteplus.server:app --reload --host 0.0.0.0 --port 8000
```

### **🔹 Acceder a la Documentación Interactiva**
Abre en tu navegador: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## 📜 Licencia
Este proyecto está bajo la licencia **MIT**.

---

## 🤝 Contribuciones
¡Las contribuciones son bienvenidas! Si deseas mejorar SQLitePlus, haz un fork del repositorio y envía un pull request. 🚀

---

## 📧 Contacto
Si tienes dudas o sugerencias, puedes contactarme en **[tuemail@example.com](mailto:tuemail@example.com)** o abrir un issue en GitHub.

