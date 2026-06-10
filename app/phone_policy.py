import os


def enforce_unique_phone() -> bool:
    """Si False, el mismo celular puede verificarse en varias cuentas (pruebas)."""
    raw = os.environ.get("ENFORCE_UNIQUE_PHONE", "").strip().lower()
    if raw in ("1", "true", "yes"):
        return True
    if raw in ("0", "false", "no"):
        return False
    return os.environ.get("ENVIRONMENT") != "development"
