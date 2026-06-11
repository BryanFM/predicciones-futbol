import app.env  # noqa: F401 — carga .env antes de leer os.environ
import os

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, sessionmaker

_url = os.environ.get("DATABASE_URL", "sqlite:///./predicciones.db")
# Render/Heroku entregan "postgres://..." pero SQLAlchemy requiere "postgresql://..."
if _url.startswith("postgres://"):
    _url = _url.replace("postgres://", "postgresql://", 1)

_connect_args: dict = {}
_engine_kwargs: dict = {}
if _url.startswith("sqlite"):
    _connect_args["check_same_thread"] = False
else:
    _connect_args["connect_timeout"] = 10
    _engine_kwargs["pool_pre_ping"] = True
    _engine_kwargs["pool_recycle"] = 300

engine = create_engine(_url, connect_args=_connect_args, **_engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    pass


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
