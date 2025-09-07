"""
Database module for Discord Bot
Database connection management and model definitions
"""
import asyncio
import logging
from typing import Optional, Generator
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from structlog import get_logger

from config import settings
from models import Base  # Shared models with Flask API

logger = get_logger()

# Global database objects
sync_engine = None
async_engine = None
sync_session_maker = None
async_session_maker = None

class DatabaseManager:
    """Database connection and session manager"""
    
    def __init__(self, database_url: str, pool_size: int = 5, max_overflow: int = 10, echo: bool = False):
        self.database_url = database_url
        self.pool_size = pool_size
        self.max_overflow = max_overflow
        self.echo = echo
        
        # Connection pool options
        self.pool_options = {
            'pool_pre_ping': True,
            'pool_recycle': 300,  # 5 minutes
            'pool_size': pool_size,
            'max_overflow': max_overflow,
            'pool_timeout': 30,
            'pool_reset_on_return': 'rollback',
        }
        
        if echo:
            self.pool_options['echo'] = True
    
    def create_sync_engine(self) -> 'Engine':
        """Create synchronous database engine"""
        global sync_engine
        
        if sync_engine is None:
            # Use sync connection for APScheduler job store
            sync_engine = create_engine(
                self.database_url,
                **self.pool_options,
                poolclass=NullPool if settings.DEBUG else None,
                future=True
            )
            
            # Test connection
            with sync_engine.connect() as conn:
                conn.execute(text("SELECT 1"))
                logger.info("Synchronous database connection established")
        
        return sync_engine
    
    async def create_async_engine(self) -> 'AsyncEngine':
        """Create asynchronous database engine"""
        global async_engine
        
        if async_engine is None:
            # Use asyncpg for async operations
            async_url = self.database_url.replace('postgresql://', 'postgresql+asyncpg://')
            
            async_engine = create_async_engine(
                async_url,
                **self.pool_options,
                poolclass=NullPool if settings.DEBUG else None,
                future=True,
                echo=self.echo
            )
            
            # Test connection
            async with async_engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
                logger.info("Asynchronous database connection established")
        
        return async_engine
    
    def get_sync_session_maker(self, engine: Optional['Engine'] = None) -> 'sessionmaker':
        """Get synchronous session maker"""
        global sync_session_maker
        
        if sync_session_maker is None:
            engine = engine or self.create_sync_engine()
            sync_session_maker = sessionmaker(
                bind=engine,
                expire_on_commit=False,
                autoflush=True,
                autocommit=False
            )
        
        return sync_session_maker
    
    async def get_async_session_maker(self, engine: Optional['AsyncEngine'] = None) -> 'async_sessionmaker':
        """Get asynchronous session maker"""
        global async_session_maker
        
        if async_session_maker is None:
            engine = engine or await self.create_async_engine()
            async_session_maker = async_sessionmaker(
                bind=engine,
                expire_on_commit=False,
                autoflush=True,
                class_=AsyncSession
            )
        
        return async_session_maker
    
    def get_sync_session(self, **kwargs) -> Generator[Session, None, None]:
        """Context manager for synchronous session"""
        session_maker = self.get_sync_session_maker()
        session = session_maker(**kwargs)
        try:
            yield session
            session.commit()
        except Exception:
            session.rollback()
            raise
        finally:
            session.close()
    
    async def get_async_session(self, **kwargs) -> Generator[AsyncSession, None, None]:
        """Context manager for asynchronous session"""
        session_maker = await self.get_async_session_maker()
        session = session_maker(**kwargs)
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
    
    async def create_tables(self):
        """Create database tables if they don't exist"""
        engine = await self.create_async_engine()
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Database tables created/verified")
    
    async def drop_tables(self):
        """Drop all database tables (for testing)"""
        if settings.DEBUG:
            engine = await self.create_async_engine()
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.drop_all)
            logger.info("Database tables dropped")
    
    async def execute_sql(self, sql: str, params: Dict = None, async_mode: bool = True) -> Any:
        """
        Execute raw SQL query
        
        Args:
            sql: SQL query string
            params: Query parameters
            async_mode: Use async execution
        
        Returns:
            Query result
        """
        if async_mode:
            session_maker = await self.get_async_session_maker()
            async with session_maker() as session:
                result = await session.execute(text(sql), params or {})
                return result.fetchall()
        else:
            session_maker = self.get_sync_session_maker()
            with session_maker() as session:
                result = session.execute(text(sql), params or {})
                return result.fetchall()
    
    def is_database_healthy(self) -> bool:
        """Check database health"""
        try:
            with self.get_sync_session() as session:
                session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error("Database health check failed", error=str(e))
            return False
    
    async def is_database_healthy_async(self) -> bool:
        """Check database health asynchronously"""
        try:
            session_maker = await self.get_async_session_maker()
            async with session_maker() as session:
                await session.execute(text("SELECT 1"))
                return True
        except Exception as e:
            logger.error("Async database health check failed", error=str(e))
            return False


# Initialize database manager
db_manager = DatabaseManager(
    database_url=settings.DATABASE_URL,
    pool_size=settings.DATABASE_POOL_SIZE,
    max_overflow=settings.DATABASE_MAX_OVERFLOW,
    echo=settings.DEBUG
)

def get_db_session() -> 'sessionmaker':
    """Get synchronous session maker for APScheduler"""
    return db_manager.get_sync_session_maker()

async def get_async_db_session() -> 'async_sessionmaker':
    """Get asynchronous session maker for bot operations"""
    return await db_manager.get_async_session_maker()

def get_sync_session() -> Generator[Session, None, None]:
    """Get synchronous session context manager"""
    return db_manager.get_sync_session()

async def get_async_session() -> Generator[AsyncSession, None, None]:
    """Get asynchronous session context manager"""
    return db_manager.get_async_session()

# Database initialization functions
async def init_database():
    """Initialize database connections and create tables"""
    global sync_engine, async_engine, sync_session_maker, async_session_maker
    
    try:
        # Create engines and session makers
        sync_engine = db_manager.create_sync_engine()
        async_engine = await db_manager.create_async_engine()
        sync_session_maker = db_manager.get_sync_session_maker()
        async_session_maker = await db_manager.get_async_session_maker()
        
        # Create tables
        await db_manager.create_tables()
        
        # Create APScheduler jobs table if it doesn't exist
        await create_scheduler_tables()
        
        logger.info("Database initialization completed successfully")
        return True
        
    except Exception as e:
        logger.error("Database initialization failed", error=str(e))
        return False

async def create_scheduler_tables():
    """Create tables needed for APScheduler"""
    create_jobs_table_sql = """
    CREATE TABLE IF NOT EXISTS apscheduler_jobs (
        id VARCHAR(191) NOT NULL PRIMARY KEY,
        next_run_time TIMESTAMP(53) UTC,
        job_state BYTEA NOT NULL,
        coalesce_id VARCHAR(191) NOT NULL,
        created_at TIMESTAMP(53) UTC NOT NULL
    );
    
    CREATE INDEX IF NOT EXISTS ix_apscheduler_jobs_next_run_time ON apscheduler_jobs (next_run_time);
    CREATE INDEX IF NOT EXISTS ix_apscheduler_jobs_coalesce_id ON apscheduler_jobs (coalesce_id);
    """
    
    try:
        await db_manager.execute_sql(create_jobs_table_sql)
        logger.debug("APScheduler tables verified/created")
    except Exception as e:
        logger.error("Failed to create APScheduler tables", error=str(e))
        raise

# Health check function
async def check_database_health() -> Dict[str, Any]:
    """Perform comprehensive database health check"""
    health_status = {
        'status': 'healthy',
        'sync_connection': False,
        'async_connection': False,
        'tables_exist': False,
        'timestamp': datetime.utcnow().isoformat()
    }
    
    try:
        # Check sync connection
        with get_sync_session() as session:
            session.execute(text("SELECT 1"))
            health_status['sync_connection'] = True
        
        # Check async connection
        async with get_async_session() as session:
            await session.execute(text("SELECT 1"))
            health_status['async_connection'] = True
        
        # Check if key tables exist
        table_check_sql = """
        SELECT COUNT(*) FROM information_schema.tables 
        WHERE table_schema = 'public' 
        AND table_name IN ('users', 'embed_templates', 'giveaways', 'message_stats')
        """
        
        count = await db_manager.execute_sql(table_check_sql)
        health_status['tables_exist'] = count[0][0] == 4
        
        logger.info("Database health check completed", status=health_status['status'])
        
    except Exception as e:
        health_status['status'] = 'unhealthy'
        health_status['error'] = str(e)
        logger.error("Database health check failed", error=str(e))
    
    return health_status

# Connection cleanup
def close_database_connections():
    """Close all database connections"""
    global sync_engine, async_engine
    
    if sync_engine:
        sync_engine.dispose()
        logger.info("Synchronous database connections closed")
    
    if async_engine:
        asyncio.create_task(async_engine.dispose())
        logger.info("Asynchronous database connections closed")

# Model imports (shared with Flask API)
# Note: In production, these should be shared via a common models package
try:
    from api.app.models import (
        User, AppConfig, MessageStats, VoiceStats, InviteStats,
        EmbedTemplate, PostedMessage, ConversationHistory,
        Giveaway, GiveawayEntry, GiveawayWinner,
        TrackShow, MediaSearchHistory, WatchPartyEvent, WatchPartyRSVP,
        AuditLog, DailyUserMessageStats, MonthlyUserVoiceStats
    )
except ImportError:
    logger.warning("Could not import shared models from API - using local definitions")
    # Define minimal models locally if API models are not available
    pass

# Export commonly used functions
__all__ = [
    'db_manager', 'get_db_session', 'get_async_db_session',
    'get_sync_session', 'get_async_session', 'init_database',
    'create_scheduler_tables', 'check_database_health',
    'close_database_connections', 'DatabaseManager'
]