import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy.orm import declarative_base

# Fallback to SQLite if PostgreSQL URL is not provided
# Example postgres url: "postgresql://user:password@localhost:5432/cotizacion3d"
DATABASE_URL = os.environ.get("DATABASE_URL", "sqlite:///cotizaciones.db")

engine = create_engine(
    DATABASE_URL, 
    # check_same_thread is needed only for SQLite
    connect_args={"check_same_thread": False} if "sqlite" in DATABASE_URL else {}
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
