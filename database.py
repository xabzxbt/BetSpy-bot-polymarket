"""
Async database session management using SQLAlchemy 2.0.
"""

from contextlib import asynccontextmanager
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    AsyncEngine,
    create_async_engine,
    async_sessionmaker,
)
from loguru import logger

from config import get_settings
from models import Base


class Database:
    """Database connection manager."""
    
    def __init__(self):
        self._engine: AsyncEngine | None = None
        self._session_factory: async_sessionmaker[AsyncSession] | None = None
    
    async def init(self) -> None:
        """Initialize database engine and session factory."""
        settings = get_settings()
        
        # Create async engine
        self._engine = create_async_engine(
            settings.database_url,
            echo=settings.log_level == "DEBUG",
            pool_pre_ping=True,
            pool_size=5,
            max_overflow=10,
        )
        
        # Create session factory
        self._session_factory = async_sessionmaker(
            bind=self._engine,
            class_=AsyncSession,
            expire_on_commit=False,
            autocommit=False,
            autoflush=False,
        )
        
        logger.info("Database engine initialized")
    
    async def create_tables(self) -> None:
        """Create all tables in the database."""
        if not self._engine:
            raise RuntimeError("Database not initialized. Call init() first.")
        
        async with self._engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        
        logger.info("Database tables created")
    
    async def close(self) -> None:
        """Close database connections."""
        if self._engine:
            await self._engine.dispose()
            logger.info("Database connections closed")
    
    @asynccontextmanager
    async def session(self) -> AsyncGenerator[AsyncSession, None]:
        """
        Get a database session context manager.
        
        Usage:
            async with db.session() as session:
                # use session
        """
        if not self._session_factory:
            raise RuntimeError("Database not initialized. Call init() first.")
        
        session = self._session_factory()
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    
    @property
    def session_factory(self) -> async_sessionmaker[AsyncSession]:
        """Get the session factory for dependency injection."""
        if not self._session_factory:
            raise RuntimeError("Database not initialized. Call init() first.")
        return self._session_factory


# Global database instance
db = Database()


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency for getting database session.
    
    Usage in handlers:
        session = await anext(get_session())
    """
    async with db.session() as session:
        yield session
