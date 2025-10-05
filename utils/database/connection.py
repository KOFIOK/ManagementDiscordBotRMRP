"""
Database connection management for PostgreSQL
Simplified version using only SQLAlchemy
"""
import asyncio
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base
from sqlalchemy import text
import os
from typing import Optional
from dotenv import load_dotenv

# Загружаем переменные окружения
load_dotenv()

# SQLAlchemy Base for models
Base = declarative_base()

class DatabaseConnection:
    """Manages database connection using SQLAlchemy only"""
    
    def __init__(self):
        self.engine = None
        self.session_factory = None
        
        # PostgreSQL configuration from environment variables
        self.host = os.getenv('POSTGRES_HOST', '127.0.0.1')
        self.port = os.getenv('POSTGRES_PORT', '5432')
        self.database = os.getenv('POSTGRES_DB', 'postgres')
        self.username = os.getenv('POSTGRES_USER', 'postgres')
        self.password = os.getenv('POSTGRES_PASSWORD', 'simplepassword')
        
        # Build connection URL (using asyncpg with direct IP)
        # Use direct IP to avoid DNS issues
        direct_host = "127.0.0.1" if self.host in ["localhost", "127.0.0.1"] else self.host
        self.async_url = f"postgresql+asyncpg://{self.username}:{self.password}@{direct_host}:{self.port}/{self.database}"
        print(f"🔧 Using PostgreSQL database: {self.database}@{self.host}")
    
    async def initialize(self) -> bool:
        """Initialize database connections"""
        try:
            print("🔗 Initializing PostgreSQL connections...")
            
            # Create SQLAlchemy async engine
            self.engine = create_async_engine(
                self.async_url,
                echo=False,  # Set to True for SQL debugging
                pool_size=10,
                max_overflow=20,
                pool_recycle=3600,  # Recycle connections every hour
                pool_pre_ping=True   # Validate connections before use
            )
            
            # Create session factory
            self.session_factory = async_sessionmaker(
                bind=self.engine,
                class_=AsyncSession,
                expire_on_commit=False
            )
            
            # Test connection
            await self.test_connection()
            print("✅ PostgreSQL connections initialized successfully!")
            return True
            
        except Exception as e:
            print(f"❌ Failed to initialize PostgreSQL connections: {e}")
            return False
    
    async def test_connection(self):
        """Test database connection"""
        try:
            async with self.engine.begin() as conn:
                result = await conn.execute(text("SELECT 1 as test"))
                value = result.scalar()
                if value != 1:
                    raise Exception("Database connection test failed")
                print("🔍 PostgreSQL connection test passed")
        except Exception as e:
            print(f"❌ Connection test failed: {e}")
            raise
    
    def get_session(self) -> AsyncSession:
        """Get async SQLAlchemy session"""
        if not self.session_factory:
            raise Exception("Database not initialized")
        return self.session_factory()
    
    async def close(self):
        """Close all database connections"""
        try:
            if self.engine:
                await self.engine.dispose()
                print("🔒 SQLAlchemy engine disposed")
                
        except Exception as e:
            print(f"⚠️ Error closing database connections: {e}")

# Global database connection instance
db_connection = DatabaseConnection()

# Compatibility function for get_database_connection
async def get_database_connection():
    """Get database engine for compatibility with existing code"""
    if not db_connection.engine:
        await db_connection.initialize()
    return db_connection.engine