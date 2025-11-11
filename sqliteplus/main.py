from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI

if __name__ == "__main__" and __package__ in {None, ""}:
    import sys
    from pathlib import Path
    from runpy import run_module

    package_root = Path(__file__).resolve().parent.parent
    if str(package_root) not in sys.path:
        sys.path.insert(0, str(package_root))
    run_module("sqliteplus.main", run_name="__main__")
    raise SystemExit()

from sqliteplus.api.endpoints import router
from sqliteplus.core.db import db_manager


@asynccontextmanager
async def lifespan(app: FastAPI):
    yield
    await db_manager.close_connections()


app = FastAPI(
    title="SQLitePlus Enhanced",
    description="API modular con JWT, SQLCipher y FastAPI.",
    version="1.0.0",
    lifespan=lifespan
)

# Registrar endpoints
app.include_router(router)
