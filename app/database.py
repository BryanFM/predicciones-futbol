import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

_url = os.environ.get("DATABASE_URL", "sqlite:///./predicciones.db")
# Render/Heroku entregan "postgres://..." pero SQLAlchemy requiere "postgresql://..."
if _url.startswith("postgres://"):
    _url = _url.replace("postgres://", "postgresql://", 1)

_kwargs = {"check_same_thread": False} if _url.startswith("sqlite") else {}
engine = create_engine(_url, connect_args=_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
