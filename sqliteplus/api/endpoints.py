from __future__ import annotations

if __name__ == "__main__" and __package__ in {None, ""}:
    import sys
    from pathlib import Path
    from runpy import run_module

    package_root = Path(__file__).resolve().parents[2]
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    run_module("sqliteplus.api.endpoints", run_name="__main__")
    raise SystemExit()

import logging
from typing import Sequence

import aiosqlite
from sqlite3 import OperationalError
from fastapi import APIRouter, HTTPException, Depends, Request
from fastapi.security import OAuth2PasswordRequestForm

from sqliteplus.core.db import db_manager
from sqliteplus.core.schemas import (
    CreateTableSchema,
    InsertDataSchema,
    is_valid_sqlite_identifier,
)
from sqliteplus.auth.jwt import generate_jwt, verify_jwt
from sqliteplus.auth.users import get_user_service, UserSourceError
from sqliteplus.auth.rate_limit import login_rate_limiter
from sqliteplus.utils.json_serialization import normalize_json_value

router = APIRouter()
logger = logging.getLogger(__name__)


def build_safe_http_error(
    *,
    status_code: int,
    public_detail: str,
    log_message: str,
    exc: Exception | None = None,
    **context: object,
) -> HTTPException:
    """Construye un HTTPException seguro para cliente y deja detalles en logs."""

    if exc is not None:
        logger.exception(log_message, extra={"context": context})
    else:
        logger.error(log_message, extra={"context": context})
    return HTTPException(status_code=status_code, detail=public_detail)


def _escape_identifier(identifier: str) -> str:
    """Escapa identificadores siguiendo las reglas de SQLite."""

    escaped_identifier = identifier.replace('"', '""')
    return f'"{escaped_identifier}"'


def _normalize_rows_response(
    column_names: Sequence[str] | None,
    rows: Sequence[Sequence[object]],
) -> dict[str, list]:
    """Convierte filas crudas en datos listos para serializar en JSON.

    A partir de esta versión la clave ``data`` actúa como alias de ``rows``
    para mantener compatibilidad con clientes anteriores que consumían dicho
    nombre.
    """

    normalized_rows = [
        [normalize_json_value(value) for value in row]
        for row in rows
    ]

    normalized_columns = list(column_names or [])
    if not normalized_columns and normalized_rows:
        normalized_columns = [
            f"columna {index + 1}" for index in range(len(normalized_rows[0]))
        ]

    normalized_response = {
        "columns": normalized_columns,
        "rows": normalized_rows,
    }
    normalized_response["data"] = normalized_rows
    return normalized_response


def _map_sql_error(exc: Exception, table_name: str) -> HTTPException:
    """Mapea errores operacionales de SQLite a respuestas HTTP apropiadas."""

    message = str(exc)
    normalized = message.lower()

    if "no such table" in normalized:
        return HTTPException(status_code=404, detail=f"Tabla '{table_name}' no encontrada")

    if "no such column" in normalized or "has no column named" in normalized:
        return build_safe_http_error(
            status_code=400,
            public_detail=f"La operación hace referencia a una columna inválida en la tabla '{table_name}'",
            log_message="Error SQL por columna inválida en tabla '%s': %s" % (table_name, message),
            exc=exc,
            table_name=table_name,
        )

    if "may not be dropped" in normalized:
        return build_safe_http_error(
            status_code=400,
            public_detail=f"No se puede eliminar la tabla '{table_name}'",
            log_message="Error SQL al eliminar tabla protegida '%s': %s" % (table_name, message),
            exc=exc,
            table_name=table_name,
        )

    if "syntax error" in normalized:
        return build_safe_http_error(
            status_code=400,
            public_detail="La operación no pudo completarse por una sintaxis SQL inválida",
            log_message="Error de sintaxis SQL en tabla '%s': %s" % (table_name, message),
            exc=exc,
            table_name=table_name,
        )

    if "more than one primary key" in normalized:
        return build_safe_http_error(
            status_code=400,
            public_detail=f"Definición inválida de clave primaria para la tabla '{table_name}'",
            log_message="Error SQL de clave primaria duplicada en tabla '%s': %s" % (table_name, message),
            exc=exc,
            table_name=table_name,
        )

    return build_safe_http_error(
        status_code=500,
        public_detail="Error interno al ejecutar la operación en la base de datos",
        log_message=(
            "Error operacional inesperado durante operación SQL en la tabla "
            f"'{table_name}': {message}"
        ),
        exc=exc,
        table_name=table_name,
    )


def _map_insert_integrity_error(exc: Exception, table_name: str) -> HTTPException:
    """Mapea violaciones de integridad en inserciones a mensajes seguros."""

    normalized = str(exc).lower()

    if "unique" in normalized:
        public_detail = "No se pudo insertar por restricción de unicidad"
    elif "foreign key" in normalized:
        public_detail = "No se pudo insertar por restricción de referencia"
    elif "not null" in normalized:
        public_detail = "No se pudo insertar por campos obligatorios faltantes"
    else:
        public_detail = "No se pudo insertar por restricción de datos"

    return build_safe_http_error(
        status_code=409,
        public_detail=public_detail,
        log_message="Error de integridad al insertar en tabla '%s'" % table_name,
        exc=exc,
        table_name=table_name,
    )

@router.post("/token", tags=["Autenticación"], summary="Obtener un token de autenticación", description="Genera un token JWT válido por 1 hora.")
async def login(request: Request, form_data: OAuth2PasswordRequestForm = Depends()):
    client_ip = request.client.host if request.client else "unknown"
    username = form_data.username or None

    if login_rate_limiter.is_blocked(ip=client_ip, username=username):
        logger.warning(
            "Intento de autenticación bloqueado por rate limit",
            extra={"context": {"username": username, "client_ip": client_ip}},
        )
        raise HTTPException(
            status_code=401,
            detail="No se pudo completar la autenticación",
            headers={"WWW-Authenticate": "Bearer"},
        )
    try:
        user_service = get_user_service()
    except UserSourceError as exc:
        raise build_safe_http_error(
            status_code=500,
            public_detail="No se pudo inicializar el servicio de autenticación",
            log_message="Fallo al obtener el servicio de usuarios para login",
            exc=exc,
            username=form_data.username,
        ) from exc

    try:
        if user_service.verify_credentials(form_data.username, form_data.password):
            try:
                token = generate_jwt(form_data.username)
            except RuntimeError as exc:
                raise build_safe_http_error(
                    status_code=500,
                    public_detail="No se pudo generar el token de autenticación",
                    log_message="Fallo al generar JWT para el usuario '%s'" % form_data.username,
                    exc=exc,
                    username=form_data.username,
                ) from exc
            login_rate_limiter.register_success(ip=client_ip, username=username)
            return {"access_token": token, "token_type": "bearer"}
    except UserSourceError as exc:
        raise build_safe_http_error(
            status_code=500,
            public_detail="No se pudieron verificar las credenciales en este momento",
            log_message="Fallo verificando credenciales del usuario '%s'" % form_data.username,
            exc=exc,
            username=form_data.username,
        ) from exc

    login_rate_limiter.register_failure(ip=client_ip, username=username)
    logger.warning(
        "Intento de autenticación fallido",
        extra={"context": {"username": username, "client_ip": client_ip}},
    )
    raise HTTPException(
        status_code=401,
        detail="No se pudo completar la autenticación",
        headers={"WWW-Authenticate": "Bearer"},
    )


@router.post("/databases/{db_name:path}/create_table", tags=["Gestión de Base de Datos"], summary="Crear una tabla", description="Crea una tabla en la base de datos especificada.")
async def create_table(db_name: str, table_name: str, schema: CreateTableSchema, user: str = Depends(verify_jwt)):
    if not is_valid_sqlite_identifier(table_name):
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
    except (OperationalError, aiosqlite.OperationalError) as exc:
        raise _map_sql_error(exc, table_name) from exc
    return {"message": f"Tabla '{table_name}' creada en la base '{db_name}'."}


@router.post("/databases/{db_name:path}/insert", tags=["Operaciones CRUD"], summary="Insertar datos", description="Inserta un registro en una tabla.")
async def insert_data(db_name: str, table_name: str, schema: InsertDataSchema, user: str = Depends(verify_jwt)):
    if not is_valid_sqlite_identifier(table_name):
        raise HTTPException(status_code=400, detail="Nombre de tabla inválido")

    payload_values = schema.values
    columns = list(payload_values.keys())
    escaped_columns = ", ".join(_escape_identifier(column) for column in columns)
    placeholders = ", ".join(["?"] * len(columns))
    query = (
        f"INSERT INTO {_escape_identifier(table_name)} ({escaped_columns}) "
        f"VALUES ({placeholders})"
    )
    try:
        params = tuple(payload_values[column] for column in columns)
        row_id = await db_manager.execute_query(
            db_name,
            query,
            params,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except aiosqlite.IntegrityError as exc:
        raise _map_insert_integrity_error(exc, table_name) from exc
    except (OperationalError, aiosqlite.OperationalError) as exc:
        raise _map_sql_error(exc, table_name) from exc
    return {"message": "Datos insertados", "row_id": row_id}



@router.get("/databases/{db_name:path}/fetch", tags=["Operaciones CRUD"], summary="Consultar datos", description="Recupera todos los registros de una tabla.")
async def fetch_data(db_name: str, table_name: str, user: str = Depends(verify_jwt)):
    if not is_valid_sqlite_identifier(table_name):
        raise HTTPException(status_code=400, detail="Nombre de tabla inválido")

    query = f"SELECT * FROM {_escape_identifier(table_name)}"
    try:
        column_names, rows = await db_manager.fetch_query_with_columns(db_name, query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (OperationalError, aiosqlite.OperationalError) as exc:
        raise _map_sql_error(exc, table_name) from exc

    return _normalize_rows_response(column_names, rows)


@router.delete("/databases/{db_name:path}/drop_table", tags=["Gestión de Base de Datos"], summary="Eliminar tabla", description="Elimina una tabla de la base de datos.")
async def drop_table(db_name: str, table_name: str, user: str = Depends(verify_jwt)):
    if not is_valid_sqlite_identifier(table_name):
        raise HTTPException(status_code=400, detail="Nombre de tabla inválido")

    query = f"DROP TABLE IF EXISTS {_escape_identifier(table_name)}"
    try:
        await db_manager.execute_query(db_name, query)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except (OperationalError, aiosqlite.OperationalError) as exc:
        raise _map_sql_error(exc, table_name) from exc
    return {"message": f"Tabla '{table_name}' eliminada de la base '{db_name}'."}
