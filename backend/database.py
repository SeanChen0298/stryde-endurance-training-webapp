from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.orm import DeclarativeBase
from sqlalchemy.pool import NullPool

from config import settings


# Serverless instances are frozen between requests, so pooled connections go
# stale; open one per session instead (Neon's pooler does the pooling).
_pool_args = (
    {"poolclass": NullPool}
    if settings.VERCEL
    else {"pool_pre_ping": True, "pool_size": 5, "max_overflow": 10}
)

engine = create_async_engine(
    settings.DATABASE_URL,
    echo=False,
    connect_args={"ssl": "require"},
    **_pool_args,
)

AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)


class Base(DeclarativeBase):
    pass


async def get_db():
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
