"""Hora de Perú (PET, UTC-5 sin horario de verano)."""
from datetime import datetime, timedelta, timezone

PERU_TZ = timezone(timedelta(hours=-5))


def peru_now() -> datetime:
    """Datetime naive en hora Perú, para comparar con match_date almacenado en PET."""
    return datetime.now(PERU_TZ).replace(tzinfo=None)


def format_pet(dt: datetime) -> str:
    return dt.strftime("%d/%m/%Y %H:%M") + " PET"


def pet_timestamp_ms(dt: datetime) -> int:
    """Epoch en milisegundos para countdown JS (datetime naive en PET)."""
    aware = dt.replace(tzinfo=PERU_TZ)
    return int(aware.timestamp() * 1000)
