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

_ADMIN_EMAILS = {
    e.strip().lower()
    for e in os.environ.get("ADMIN_EMAILS", "").split(",")
    if e.strip()
}


def get_current_user(request: Request, db: Session = Depends(get_db)) -> Optional[User]:
    user_id = request.session.get("user_id")
    if not user_id:
        return None
    return db.get(User, user_id)


def require_login(user: Optional[User] = Depends(get_current_user)) -> User:
    if not user:
        raise HTTPException(401, "Debes iniciar sesión")
    return user


def require_admin(user: Optional[User] = Depends(get_current_user)) -> User:
    if not user or not user.is_admin:
        raise HTTPException(403, "Acceso restringido a administradores")
    return user


def upsert_user(db: Session, google_id: str, email: str, name: str, picture: str) -> User:
    user = db.query(User).filter(User.google_id == google_id).first()
    if user:
        user.name = name
        user.picture = picture
        db.commit()
        return user

    is_admin = email.lower() in _ADMIN_EMAILS
    user = User(google_id=google_id, email=email, name=name, picture=picture, is_admin=is_admin)
    db.add(user)
    db.commit()
    db.refresh(user)
    return user
