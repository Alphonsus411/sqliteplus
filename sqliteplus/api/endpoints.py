from sqlite3 import OperationalError
from fastapi import APIRouter, HTTPException, Depends, Body
from fastapi.security import OAuth2PasswordRequestForm

from sqliteplus.core.db import db_manager
from sqliteplus.core.schemas import CreateTableSchema, InsertDataSchema
from sqliteplus.auth.jwt import generate_jwt, verify_jwt

router = APIRouter()


def _escape_identifier(identifier: str) -> str:
    """Escapa identificadores siguiendo las reglas de SQLite."""

    return f'"{identifier.replace("\"", "\"\"")}"'

@router.post("/token", tags=["Autenticación"], summary="Obtener un token de autenticación", description="Genera un token JWT válido por 1 hora.")
async def login(form_data: OAuth2PasswordRequestForm = Depends()):
    if form_data.username == "admin" and form_data.password == "admin":
        token = generate_jwt(form_data.username)
        return {"access_token": token, "token_type": "bearer"}
    raise HTTPException(status_code=400, detail="Credenciales incorrectas")


@router.post("/databases/{db_name:path}/create_table", tags=["Gestión de Base de Datos"], summary="Crear una tabla", description="Crea una tabla en la base de datos especificada.")
async def create_table(db_name: str, table_name: str, schema: CreateTableSchema, user: str = Depends(verify_jwt)):
    if not table_name.isidentifier():
        raise HTTPException(status_code=400, detail="Nombre de tabla inválido")

    try:
        sanitized_columns = schema.normalized_columns()
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    columns_def = ", ".join(
        f"{_escape_identifier(column)} {column_type}" for column, column_type in sanitized_columns.items()
    )
    query = f"CREATE TABLE IF NOT EXISTS {_escape_identifier(table_name)} ({columns_def})"
    try:
        await db_manager.execute_query(db_name, query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": f"Tabla '{table_name}' creada en la base '{db_name}'."}


@router.post("/databases/{db_name:path}/insert", tags=["Operaciones CRUD"], summary="Insertar datos", description="Inserta un registro en una tabla.")
async def insert_data(db_name: str, table_name: str, schema: InsertDataSchema, user: str = Depends(verify_jwt)):
    if not table_name.isidentifier():
        raise HTTPException(status_code=400, detail="Nombre de tabla inválido")

    query = f'INSERT INTO "{table_name}" (msg) VALUES (?)'
    try:
        row_id = await db_manager.execute_query(db_name, query, (schema.msg,))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": "Datos insertados", "row_id": row_id}



@router.get("/databases/{db_name:path}/fetch", tags=["Operaciones CRUD"], summary="Consultar datos", description="Recupera todos los registros de una tabla.")
async def fetch_data(db_name: str, table_name: str, user: str = Depends(verify_jwt)):
    if not table_name.isidentifier():
        raise HTTPException(status_code=400, detail="Nombre de tabla inválido")

    query = f'SELECT * FROM "{table_name}"'
    try:
        data = await db_manager.fetch_query(db_name, query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except OperationalError:
        raise HTTPException(status_code=404, detail=f"Tabla '{table_name}' no encontrada")
    return {"data": data}


@router.delete("/databases/{db_name:path}/drop_table", tags=["Gestión de Base de Datos"], summary="Eliminar tabla", description="Elimina una tabla de la base de datos.")
async def drop_table(db_name: str, table_name: str, user: str = Depends(verify_jwt)):
    if not table_name.isidentifier():
        raise HTTPException(status_code=400, detail="Nombre de tabla inválido")

    query = f'DROP TABLE IF EXISTS "{table_name}"'
    try:
        await db_manager.execute_query(db_name, query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"message": f"Tabla '{table_name}' eliminada de la base '{db_name}'."}
