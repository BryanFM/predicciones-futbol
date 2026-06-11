"""Carga variables de entorno desde .env (solo desarrollo local)."""
from pathlib import Path


def load_env(*, override: bool = False) -> None:
    try:
        from dotenv import load_dotenv
    except ImportError:
        return

    root = Path(__file__).resolve().parent.parent
    load_dotenv(root / ".env", override=override)
    load_dotenv(root / ".env.local", override=True)


load_env()


def refresh_env() -> None:
    """Relee .env (útil en desarrollo tras editar variables sin reiniciar uvicorn)."""
    load_env(override=True)
