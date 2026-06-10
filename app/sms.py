import hashlib
import logging
import os
import random
import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.models import PhoneVerification

logger = logging.getLogger("uvicorn.error")

OTP_EXPIRY_MINUTES = 10
OTP_MAX_ATTEMPTS = 5
DEV_OTP_CODE = "123456"


def normalize_phone(raw: str, default_country: str = "+51") -> str:
    """Normaliza a E.164. Perú móvil: +51 + 9 dígitos (empiezan en 9)."""
    cc = default_country.lstrip("+")  # "51"
    digits = re.sub(r"\D", "", raw.strip())

    if digits.startswith("00"):
        digits = digits[2:]

    # Quitar código de país repetido (5151…)
    while digits.startswith(cc + cc):
        digits = digits[len(cc):]

    if digits.startswith(cc):
        local = digits[len(cc):].lstrip("0")
        if len(local) == 9 and local[0] == "9":
            return f"+{cc}{local}"
        if local:
            return f"+{cc}{local}"

    # Local con 0 inicial: 0987654321 → 987654321
    if len(digits) == 10 and digits.startswith("0") and digits[1] == "9":
        digits = digits[1:]

    digits = digits.lstrip("0")

    if len(digits) == 9 and digits[0] == "9":
        return f"+{cc}{digits}"

    if raw.strip().startswith("+"):
        return "+" + re.sub(r"\D", "", raw.strip())

    return f"+{cc}{digits}"


def _twilio_configured() -> bool:
    return bool(
        os.environ.get("TWILIO_ACCOUNT_SID")
        and os.environ.get("TWILIO_AUTH_TOKEN")
        and os.environ.get("TWILIO_VERIFY_SERVICE_SID")
    )


def _use_twilio_sms() -> bool:
    return _twilio_configured()


def twilio_is_configured() -> bool:
    return _twilio_configured()


def is_development_sms() -> bool:
    return os.environ.get("ENVIRONMENT") == "development"


def _twilio_error_message(exc: Exception, phone: str = "") -> str:
    msg = str(exc).lower()
    if "unverified" in msg and "trial" in msg:
        hint = f" Número enviado: {phone}." if phone else ""
        return (
            "Cuenta Twilio de prueba: el número debe estar verificado en "
            "twilio.com/user/account/phone-numbers/verified con el mismo formato "
            f"(E.164, ej. +519XXXXXXXX).{hint}"
        )
    if "permission to send an sms has not been enabled" in msg:
        return "Twilio no tiene permiso SMS para Perú (+51). Actívalo en Geo Permissions."
    if phone:
        return f"No se pudo enviar el SMS a {phone}. Intenta más tarde."
    return "No se pudo enviar el SMS. Intenta más tarde."


def _hash_code(code: str) -> str:
    return hashlib.sha256(code.encode()).hexdigest()


def send_verification_code(db: Session, user_id: int, phone: str) -> Tuple[bool, str]:
    phone = normalize_phone(phone)

    if _use_twilio_sms():
        try:
            from twilio.rest import Client

            client = Client(
                os.environ["TWILIO_ACCOUNT_SID"],
                os.environ["TWILIO_AUTH_TOKEN"],
            )
            client.verify.v2.services(
                os.environ["TWILIO_VERIFY_SERVICE_SID"]
            ).verifications.create(to=phone, channel="sms")
            _store_pending(db, user_id, phone, twilio=True)
            return True, f"Código enviado por SMS a {phone}."
        except Exception as exc:
            logger.error("Twilio error para %s: %s", phone, exc)
            return False, _twilio_error_message(exc, phone)

    code = DEV_OTP_CODE if os.environ.get("ENVIRONMENT") == "development" else f"{random.randint(100000, 999999)}"
    _store_pending(db, user_id, phone, code=code, twilio=False)
    if os.environ.get("ENVIRONMENT") == "development":
        logger.warning("DEV OTP para %s: %s", phone, code)
        return True, f"Modo desarrollo: usa el código {code}"
    return True, "Código enviado por SMS."


def _store_pending(
    db: Session,
    user_id: int,
    phone: str,
    code: Optional[str] = None,
    twilio: bool = False,
) -> None:
    db.query(PhoneVerification).filter(PhoneVerification.user_id == user_id).delete()
    entry = PhoneVerification(
        user_id=user_id,
        phone_number=phone,
        code_hash=_hash_code(code) if code else None,
        uses_twilio=twilio,
        expires_at=datetime.utcnow() + timedelta(minutes=OTP_EXPIRY_MINUTES),
    )
    db.add(entry)
    db.commit()


def verify_code(db: Session, user_id: int, phone: str, code: str) -> Tuple[bool, str]:
    phone = normalize_phone(phone)
    entry = (
        db.query(PhoneVerification)
        .filter(PhoneVerification.user_id == user_id)
        .order_by(PhoneVerification.created_at.desc())
        .first()
    )

    if not entry or entry.phone_number != phone:
        return False, "Solicita un código primero."
    if entry.expires_at < datetime.utcnow():
        return False, "El código expiró. Solicita uno nuevo."
    if entry.attempts >= OTP_MAX_ATTEMPTS:
        return False, "Demasiados intentos. Solicita un código nuevo."

    entry.attempts += 1
    db.commit()

    if entry.uses_twilio:
        if not _twilio_configured():
            return False, "Servicio SMS no configurado."
        try:
            from twilio.rest import Client

            client = Client(
                os.environ["TWILIO_ACCOUNT_SID"],
                os.environ["TWILIO_AUTH_TOKEN"],
            )
            check = client.verify.v2.services(
                os.environ["TWILIO_VERIFY_SERVICE_SID"]
            ).verification_checks.create(to=phone, code=code.strip())
            if check.status != "approved":
                return False, "Código incorrecto."
        except Exception as exc:
            logger.error("Twilio verify error: %s", exc)
            return False, "No se pudo verificar el código."
    else:
        if _hash_code(code.strip()) != entry.code_hash:
            return False, "Código incorrecto."

    db.query(PhoneVerification).filter(PhoneVerification.user_id == user_id).delete()
    db.commit()
    return True, "Teléfono verificado correctamente."
