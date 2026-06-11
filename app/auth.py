import app.env  # noqa: F401
import os
from typing import Optional

from authlib.integrations.starlette_client import OAuth
from fastapi import Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.database import get_db
from app.models import User

oauth = OAuth()
oauth.register(
    name="google",
    client_id=os.environ.get("GOOGLE_CLIENT_ID", ""),
    client_secret=os.environ.get("GOOGLE_CLIENT_SECRET", ""),
    server_metadata_url="https://accounts.google.com/.well-known/openid-configuration",
    client_kwargs={"scope": "openid email profile"},
)

def _admin_emails() -> set[str]:
    return {
        e.strip().lower()
        for e in os.environ.get("ADMIN_EMAILS", "").split(",")
        if e.strip()
    }


def _should_be_admin(email: str) -> bool:
    return email.strip().lower() in _admin_emails()


def sync_admin_flag(db: Session, user: User) -> User:
    """Mantiene is_admin alineado con ADMIN_EMAILS (sin exigir nuevo login)."""
    should = _should_be_admin(user.email)
    if user.is_admin != should:
        user.is_admin = should
        db.commit()
        db.refresh(user)
    return user


def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    user = db.get(User, user_id)
    if not user:
        return None
    return sync_admin_flag(db, user)


def require_login(user: Optional[User] = Depends(get_current_user)) -> User:
    if not user:
        raise HTTPException(401, "Debes iniciar sesión")
    return user


def require_admin(user: Optional[User] = Depends(get_current_user)) -> User:
    if not user or not user.is_admin:
        raise HTTPException(403, "Acceso restringido a administradores")
    return user


def require_verified(user: User = Depends(require_login)) -> User:
    if not user.phone_verified:
        raise HTTPException(403, "Debes verificar tu número de celular")
    return user


def upsert_user(
    db: Session,
    google_id: str,
    email: str,
    name: str,
    picture: str,
    referred_by_id: Optional[int] = None,
) -> User:
    should_be_admin = _should_be_admin(email)
    user = db.query(User).filter(User.google_id == google_id).first()
    if user:
        user.name = name
        user.picture = picture
        user.email = email
        user.is_admin = should_be_admin
        from app.referrals import apply_referred_by, ensure_referral_code

        apply_referred_by(db, user, referred_by_id)
        ensure_referral_code(db, user)
        db.commit()
        db.refresh(user)
        return user

    from app.referrals import ensure_referral_code, generate_referral_code

    ref_id = referred_by_id
    if ref_id:
        referrer = db.get(User, ref_id)
        if not referrer or referrer.email.lower() == email.lower():
            ref_id = None

    user = User(
        google_id=google_id,
        email=email,
        name=name,
        picture=picture,
        is_admin=should_be_admin,
        referral_code=generate_referral_code(db),
        referred_by_id=ref_id,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
