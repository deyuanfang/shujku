from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from app.config import settings

engine = create_async_engine(
    settings.database_url,
    echo=settings.debug,
    connect_args={"check_same_thread": False},
)

async_session = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


async def get_db() -> AsyncSession:
    """Dependency that provides an async database session."""
    async with async_session() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def init_db():
    """Create all tables and FTS5 index. Call on startup."""
    from app.database.models import Base, FTS5_SETUP_SQL
    from app.services.ai_action_logger import AIActionLog  # ensure table creation

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # FTS5 virtual table — use raw aiosqlite connection
    import aiosqlite
    import os
    db_path = settings.database_url.replace("sqlite+aiosqlite:///", "")
    async with aiosqlite.connect(db_path) as db:
        for stmt in FTS5_SETUP_SQL.strip().split(";"):
            stmt = stmt.strip()
            if stmt:
                try:
                    await db.execute(stmt)
                except Exception:
                    pass  # Already exists
        await db.commit()
