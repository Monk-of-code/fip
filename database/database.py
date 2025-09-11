"""
Database connection and management utilities
"""

import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.exc import SQLAlchemyError
from .models import Base
import logging

logger = logging.getLogger(__name__)

def get_database_url():
    """Get database URL from environment variables"""
    return os.getenv('DATABASE_URL', 'postgresql://airflow:airflow@postgres:5432/airflow')

def get_db_session():
    """Create a database session"""
    try:
        database_url = get_database_url()
        engine = create_engine(database_url)
        SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
        return SessionLocal()
    except Exception as e:
        logger.error(f"Failed to create database session: {e}")
        raise

def create_tables():
    """Create all database tables"""
    try:
        database_url = get_database_url()
        engine = create_engine(database_url)

        #enable pgcrypto for gen_random_uuid
        with engine.begin() as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS pgcrypto;")
            
        #create tables
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully")
        return True
    except SQLAlchemyError as e:
        logger.error(f"Failed to create database tables: {e}")
        return False

def test_connection():
    """Test database connection"""
    try:
        session = get_db_session()
        session.execute("SELECT 1")
        session.close()
        logger.info("Database connection test successful")
        return True
    except Exception as e:
        logger.error(f"Database connection test failed: {e}")
        return False