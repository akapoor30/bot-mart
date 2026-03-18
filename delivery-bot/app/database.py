from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
import os
from app.models import Base

# Load from .env (set DATABASE_URL there to switch between SQLite and PostgreSQL)
SQLALCHEMY_DATABASE_URL = os.getenv("DATABASE_URL", "sqlite:///./botmart.db")

# SQLite needs check_same_thread=False; PostgreSQL does not
connect_args = {"check_same_thread": False} if SQLALCHEMY_DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(SQLALCHEMY_DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Dependency to get a DB session in route handlers
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()