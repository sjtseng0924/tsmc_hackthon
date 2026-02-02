from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import settings

DATABASE_URL = settings.DATABASE_URL


# 如果是 SQLite，需要 check_same_thread=False
connect_args = {"check_same_thread": False} if "sqlite" in DATABASE_URL else {}

# 建立同步 Engine
engine = create_engine(
    DATABASE_URL, 
    echo=True, 
    connect_args=connect_args
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()

# Dependency 也改成同步 yield
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()