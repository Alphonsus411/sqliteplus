from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

from .api.endpoints import router
from .core.db import db_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await db_manager.close_connections()


app = FastAPI(
    title="SQLitePlus Enhanced",
    description="API modular con JWT, SQLCipher, Redis y FastAPI.",
    version="1.0.0",
    lifespan=lifespan
)

# Registrar endpoints
app.include_router(router)
