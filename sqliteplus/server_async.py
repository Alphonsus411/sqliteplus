from fastapi import FastAPI, HTTPException, Depends
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from sqliteplus.database_manager_async import AsyncDatabaseManager
import jwt
import datetime
import asyncio
import os
from typing import AsyncGenerator

app = FastAPI(
    title="SQLitePlus API",
    description="API mejorada con autenticación JWT, gestión de SQLite y operaciones asincrónicas.",
    version="1.0.0",
    contact={
        "name": "Adolfo González",
        "email": "adolfogonzal@gmail.com",
    },
)

db_manager = AsyncDatabaseManager()
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/token")
SECRET_KEY = os.getenv("SECRET_KEY", "clave_super_segura")

# Función para generar tokens JWT
def generate_jwt(username: str):
    expiration = datetime.datetime.utcnow() + datetime.timedelta(hours=1)
    payload = {"sub": username, "exp": expiration}
    return jwt.encode(payload, SECRET_KEY, algorithm="HS256")

# Función para validar tokens JWT
def verify_jwt(token: str = Depends(oauth2_scheme)):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
        return payload["sub"]
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="Token expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token inválido")

@app.post("/token", tags=["Autenticación"], summary="Obtener un token de autenticación", description="Genera un token JWT válido por 1 hora.")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username == "admin" and form_data.password == "admin":
        token = generate_jwt(form_data.username)
        return {"access_token": token, "token_type": "bearer"}
    raise HTTPException(status_code=400, detail="Credenciales incorrectas")

@app.post("/databases/{db_name}/create_table", tags=["Gestión de Base de Datos"], summary="Crear una tabla en la base de datos", description="Crea una tabla en la base de datos especificada. Requiere autenticación.")
async def create_table(db_name: str, table_name: str, user: str = Depends(verify_jwt)):
    if not table_name.isidentifier():
        raise HTTPException(status_code=400, detail="Nombre de tabla inválido")
    query = f'CREATE TABLE IF NOT EXISTS "{table_name}" (id INTEGER PRIMARY KEY, data TEXT)'
    await db_manager.execute_query(db_name, query)
    return {"message": f"Tabla '{table_name}' creada en la base '{db_name}'."}

@app.post("/databases/{db_name}/insert", tags=["Operaciones CRUD"], summary="Insertar datos en una tabla", description="Inserta un registro en una tabla específica. Requiere autenticación.")
async def insert_data(db_name: str, table_name: str, data: str, user: str = Depends(verify_jwt)):
    if not table_name.isidentifier():
        raise HTTPException(status_code=400, detail="Nombre de tabla inválido")
    query = f'INSERT INTO "{table_name}" (data) VALUES (?)'
    row_id = await db_manager.execute_query(db_name, query, (data,))
    return {"message": "Datos insertados", "row_id": row_id}

@app.get("/databases/{db_name}/fetch", tags=["Operaciones CRUD"], summary="Consultar datos en una tabla", description="Recupera todos los registros de una tabla. Requiere autenticación.")
async def fetch_data(db_name: str, table_name: str, user: str = Depends(verify_jwt)):
    if not table_name.isidentifier():
        raise HTTPException(status_code=400, detail="Nombre de tabla inválido")
    query = f'SELECT * FROM "{table_name}"'
    data = await db_manager.fetch_query(db_name, query)
    return {"data": data}

@app.delete("/databases/{db_name}/drop_table", tags=["Gestión de Base de Datos"], summary="Eliminar una tabla", description="Elimina una tabla de la base de datos. Requiere autenticación.")
async def drop_table(db_name: str, table_name: str, user: str = Depends(verify_jwt)):
    if not table_name.isidentifier():
        raise HTTPException(status_code=400, detail="Nombre de tabla inválido")
    query = f'DROP TABLE IF EXISTS "{table_name}"'
    await db_manager.execute_query(db_name, query)
    return {"message": f"Tabla '{table_name}' eliminada de la base '{db_name}'."}

async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    yield
    await db_manager.close_connections()

app.lifecycle = lifespan  # Se usa lifespan correctamente

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
