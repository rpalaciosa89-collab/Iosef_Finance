import os
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base

from app.config import settings

# SP-3.2: el .env del backend se carga explicitamente para que os.getenv() y
# pydantic-settings vean el mismo estado; la URL viene de la fuente unica (settings).
load_dotenv(override=False)

# Default to SQLite for local development, easily switchable to postgresql:// in production
DATABASE_URL = settings.DATABASE_URL

# For SQLite, we need connect_args={"check_same_thread": False}
connect_args = {"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {}

engine = create_engine(DATABASE_URL, connect_args=connect_args)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
