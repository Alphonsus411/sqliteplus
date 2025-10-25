from __future__ import annotations

if __package__ in {None, ""}:
    import sys
    from pathlib import Path

    _current_path = Path(__file__).resolve()
    for parent in _current_path.parents:
        if parent.name == "sqliteplus":
            project_root = parent.parent
            if str(project_root) not in sys.path:
                sys.path.insert(0, str(project_root))
            break

from contextlib import asynccontextmanager

from fastapi import FastAPI

from sqliteplus.api.endpoints import router
from sqliteplus.core.db import db_manager


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
