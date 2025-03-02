from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from sqliteplus.core import SQLitePlus

# Inicializar FastAPI y la base de datos
app = FastAPI()
db = SQLitePlus()

# Modelo de datos para recibir consultas SQL
class QueryModel(BaseModel):
    query: str
    params: list = []

@app.get("/")
def home():
    return {"message": "API SQLitePlus en funcionamiento"}

@app.post("/execute/")
def execute_query(query_data: QueryModel):
    """
    Ejecuta una consulta SQL de escritura (INSERT, UPDATE, DELETE).
    """
    result = db.execute_query(query_data.query, tuple(query_data.params))
    if result is None:
        raise HTTPException(status_code=400, detail="Error al ejecutar la consulta")
    return {"message": "Consulta ejecutada con éxito", "last_inserted_id": result}

@app.post("/fetch/")
def fetch_query(query_data: QueryModel):
    """
    Ejecuta una consulta SQL de lectura (SELECT) y devuelve los resultados.
    """
    result = db.fetch_query(query_data.query, tuple(query_data.params))
    if result is None:
        raise HTTPException(status_code=400, detail="Error al ejecutar la consulta")
    return {"data": result}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)


