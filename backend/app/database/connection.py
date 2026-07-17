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
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        # Create FTS5 virtual table and triggers
        try:
            await conn.run_sync(lambda sync_conn: sync_conn.exec_driver_sql(FTS5_SETUP_SQL))
        except Exception:
            pass  # FTS5 may already exist
