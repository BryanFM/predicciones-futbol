#!/usr/bin/env python3
"""Elimina todos los usuarios excepto KEEP_EMAIL y limpia registros de bajas."""

from __future__ import annotations

import sys

KEEP_EMAIL = "bryan.flores.magallanes@gmail.com"


def main() -> int:
    import os

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    if root not in sys.path:
        sys.path.insert(0, root)

    from app.account import delete_user_account
    from app.database import SessionLocal
    from app.models import AccountDeletion, User

    db = SessionLocal()
    try:
        keep = db.query(User).filter(User.email == KEEP_EMAIL).first()
        if not keep:
            print(f"ERROR: no existe el usuario {KEEP_EMAIL}", file=sys.stderr)
            return 1

        others = db.query(User).filter(User.id != keep.id).all()
        print(f"→ Eliminando {len(others)} usuario(s)…")
        for user in others:
            print(f"  · {user.email}")
            delete_user_account(db, user, deleted_by="admin_purge")

        deleted_logs = db.query(AccountDeletion).delete()
        db.commit()
        db.refresh(keep)

        print(f"→ Registros de bajas eliminados: {deleted_logs}")
        print(f"→ Usuario restante: {keep.email} (id={keep.id}, admin={keep.is_admin})")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
