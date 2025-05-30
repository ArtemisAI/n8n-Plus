import os
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from dotenv import load_dotenv
import logging # Added for logging

# Configure logging for this module
logger = logging.getLogger(__name__)

# Load environment variables from .env file
# This is useful for development. In production, variables might be set directly.
BASE_DIR = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
dotenv_path = os.path.join(BASE_DIR, '.env')
if os.path.exists(dotenv_path):
    logger.info(f"Loading .env file from: {dotenv_path}")
    load_dotenv(dotenv_path)
else:
    logger.info(f".env file not found at {dotenv_path}, using system environment variables.")


# Database URL Configuration
DATABASE_URL_POSTGRES = os.getenv("DATABASE_URL_POSTGRES")
DATABASE_URL_SQLITE = os.getenv("DATABASE_URL_SQLITE", "sqlite:///./n8n_templates.db") # Default SQLite

SQLALCHEMY_DATABASE_URL = DATABASE_URL_SQLITE # Default to SQLite

if DATABASE_URL_POSTGRES:
    SQLALCHEMY_DATABASE_URL = DATABASE_URL_POSTGRES
    logger.info("Using PostgreSQL database.")
else:
    logger.info("PostgreSQL environment variables not set, defaulting to SQLite.")
    logger.info(f"SQLite database path: {DATABASE_URL_SQLITE}")


try:
    engine = create_engine(
        SQLALCHEMY_DATABASE_URL,
        # connect_args are specific to SQLite, remove if causing issues with PostgreSQL
        # For PostgreSQL, other connect_args might be relevant, e.g., for SSL
        connect_args={"check_same_thread": False} if "sqlite" in SQLALCHEMY_DATABASE_URL else {}
    )
except Exception as e:
    logger.error(f"Failed to create database engine for URL: {SQLALCHEMY_DATABASE_URL}", exc_info=True)
    raise

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def create_db_and_tables():
    logger.info("Attempting to create database tables if they don't exist...")
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables checked/created successfully.")
    except Exception as e:
        logger.error(f"Error creating database tables for URL {SQLALCHEMY_DATABASE_URL}: {e}", exc_info=True)
        # Depending on the severity, you might want to exit or handle differently
        raise # Re-raise the exception to make it visible

# Example of how to get a DB session (for use in other modules)
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
