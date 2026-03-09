from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import get_settings

settings = get_settings()
engine = create_async_engine(
    settings.database_url,
    future=True,
    echo=False,
    pool_pre_ping=True,
    pool_recycle=1800,
)
SessionLocal = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
