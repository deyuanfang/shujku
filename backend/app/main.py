"""PersonalKB — FastAPI Application Entry Point"""

from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database.connection import init_db
from app.api.router import api_router


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: create tables and ensure data directories exist
    settings.upload_dir.mkdir(parents=True, exist_ok=True)
    await init_db()

    # Auto-setup: ensure core dependencies
    from app.services.auto_setup import ensure_core_deps
    await ensure_core_deps()

    # Start background analysis worker
    from app.services.task_queue import start_worker
    await start_worker()

    # Auto-configure AI provider from saved settings
    try:
        from app.database.connection import async_session
        from app.api.settings import _configure_from_db
        async with async_session() as db:
            await _configure_from_db(db)
    except Exception:
        pass

    yield

    # Shutdown: stop background worker
    from app.services.task_queue import stop_worker
    await stop_worker()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — allow Electron frontend (localhost) and any dev server
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.get("/health")
async def health_check():
    return {"status": "ok", "name": settings.app_name}
