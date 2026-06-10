from typing import Optional

from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.database import get_db
from app.models import Category, ChampionPrediction, PhoneVerification, Prediction, User, AccountDeletion, YapePurchaseRequest, YapePurchaseStatus
from app.rendering import render
from app.timezone import peru_now
from app.yape_policy import YAPE_PACKAGES, get_package

router = APIRouter(prefix="/admin", tags=["admin"])


def clear_phone_verification(db: Session, user: User) -> None:
    user.phone_verified = False
    user.phone_number = None
    user.phone_verified_at = None
    db.query(PhoneVerification).filter(PhoneVerification.user_id == user.id).delete()
    db.commit()


def _users_redirect(
    filter: Optional[str] = None,
    category_id: Optional[int] = None,
    msg: Optional[str] = None,
    error: Optional[str] = None,
) -> RedirectResponse:
    params = []
    if filter and filter != "all":
        params.append(f"filter={filter}")
    if category_id:
        params.append(f"category_id={category_id}")
    if msg:
        params.append(f"msg={msg}")
    if error:
        params.append(f"error={error}")
    qs = "&".join(params)
    return RedirectResponse(f"/admin/usuarios{'?' + qs if qs else ''}", status_code=303)


@router.get("/usuarios", response_class=HTMLResponse)
def list_users(
    request: Request,
    filter: Optional[str] = None,
    category_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    query = db.query(User).order_by(User.created_at.desc())
    if filter == "verified":
        query = query.filter(User.phone_verified.is_(True))
    elif filter == "unverified":
        query = query.filter(User.phone_verified.is_(False))

    users = query.all()
    pred_counts = dict(
        db.query(Prediction.user_id, func.count(Prediction.id))
        .group_by(Prediction.user_id)
        .all()
    )

    categories = db.query(Category).order_by(Category.name).all()
    selected_category_id = category_id or (categories[0].id if categories else None)
    selected_category = next((c for c in categories if c.id == selected_category_id), None)

    champion_by_user: dict[int, ChampionPrediction] = {}
    if selected_category_id:
        champion_rows = (
            db.query(ChampionPrediction)
            .filter(ChampionPrediction.category_id == selected_category_id)
            .all()
        )
        champion_by_user = {cp.user_id: cp for cp in champion_rows}

    total = db.query(User).count()
    verified = db.query(User).filter(User.phone_verified.is_(True)).count()
    deleted_total = db.query(AccountDeletion).count()

    return render(
        "admin/users.html",
        {
            "users": users,
            "pred_counts": pred_counts,
            "champion_by_user": champion_by_user,
            "categories": categories,
            "selected_category": selected_category,
            "selected_category_id": selected_category_id,
            "filter": filter or "all",
            "stats": {
                "total": total,
                "verified": verified,
                "unverified": total - verified,
                "deleted": deleted_total,
            },
        },
        request=request,
        db=db,
        current_user=current_user,
    )


@router.get("/bajas-cuentas", response_class=HTMLResponse)
def list_account_deletions(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    deletions = (
        db.query(AccountDeletion)
        .order_by(AccountDeletion.deleted_at.desc())
        .limit(500)
        .all()
    )
    return render(
        "admin/deletions.html",
        {
            "deletions": deletions,
            "total": db.query(AccountDeletion).count(),
        },
        request=request,
        db=db,
        current_user=current_user,
    )


@router.post("/usuarios/{user_id}/unverify-phone")
def unverify_user_phone(
    user_id: int,
    filter: Optional[str] = Form(None),
    category_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    user = db.get(User, user_id)
    if not user:
        return _users_redirect(filter, category_id, error="Usuario+no+encontrado")
    if not user.phone_verified:
        return _users_redirect(filter, category_id)
    clear_phone_verification(db, user)
    return _users_redirect(filter, category_id, msg="Verificacion+de+celular+eliminada")


@router.get("/torneos", response_class=HTMLResponse)
def list_tournaments(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    from sqlalchemy.orm import joinedload

    tournaments = (
        db.query(Category)
        .options(joinedload(Category.matches))
        .order_by(Category.name)
        .all()
    )
    return render(
        "admin/tournaments.html",
        {"tournaments": tournaments},
        request=request,
        db=db,
        current_user=current_user,
    )


@router.post("/torneos")
def create_tournament(
    name: str = Form(...),
    description: str = Form(""),
    season: str = Form(""),
    is_active: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    name = name.strip()
    if db.query(Category).filter(Category.name == name).first():
        return RedirectResponse("/admin/torneos?error=Ya+existe+ese+torneo", status_code=303)
    db.add(
        Category(
            name=name,
            description=description.strip() or None,
            season=season.strip() or None,
            is_active=is_active == "on",
        )
    )
    db.commit()
    return RedirectResponse("/admin/torneos?msg=Torneo+creado", status_code=303)


@router.post("/torneos/{tournament_id}/edit")
def edit_tournament(
    tournament_id: int,
    name: str = Form(...),
    description: str = Form(""),
    season: str = Form(""),
    starts_at: str = Form(""),
    champion_closes_at: str = Form(""),
    champion_team: str = Form(""),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    from app.services import evaluate_champion_predictions

    t = db.get(Category, tournament_id)
    if not t:
        return RedirectResponse("/admin/torneos?error=Torneo+no+encontrado", status_code=303)

    name = name.strip()
    if not name:
        return RedirectResponse("/admin/torneos?error=El+nombre+es+obligatorio", status_code=303)

    duplicate = (
        db.query(Category)
        .filter(Category.name == name, Category.id != tournament_id)
        .first()
    )
    if duplicate:
        return RedirectResponse("/admin/torneos?error=Ya+existe+otro+torneo+con+ese+nombre", status_code=303)

    t.name = name
    t.description = description.strip() or None
    t.season = season.strip() or None

    if starts_at.strip():
        parsed = starts_at.strip()
        if len(parsed) == 16:
            parsed += ":00"
        t.starts_at = datetime.fromisoformat(parsed)

    if champion_closes_at.strip():
        parsed = champion_closes_at.strip()
        if len(parsed) == 16:
            parsed += ":00"
        t.champion_closes_at = datetime.fromisoformat(parsed)

    new_champion = champion_team.strip() or None
    if new_champion != t.champion_team:
        t.champion_team = new_champion
        if new_champion:
            evaluate_champion_predictions(db, t)

    db.commit()
    return RedirectResponse("/admin/torneos?msg=Torneo+actualizado", status_code=303)


@router.post("/torneos/{tournament_id}/toggle")
def toggle_tournament(
    tournament_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    t = db.get(Category, tournament_id)
    if t:
        t.is_active = not t.is_active
        db.commit()
    return RedirectResponse("/admin/torneos", status_code=303)


@router.post("/torneos/{tournament_id}/delete")
def delete_tournament(
    tournament_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    t = db.get(Category, tournament_id)
    if t and len(t.matches) == 0:
        db.delete(t)
        db.commit()
    return RedirectResponse("/admin/torneos", status_code=303)


def _yape_redirect(
    filter: Optional[str] = None,
    msg: Optional[str] = None,
    error: Optional[str] = None,
) -> RedirectResponse:
    params = []
    if filter and filter != "all":
        params.append(f"filter={filter}")
    if msg:
        params.append(f"msg={msg}")
    if error:
        params.append(f"error={error}")
    qs = "&".join(params)
    return RedirectResponse(f"/admin/compras-yape{'?' + qs if qs else ''}", status_code=303)


@router.get("/compras-yape", response_class=HTMLResponse)
def list_yape_purchases(
    request: Request,
    filter: Optional[str] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    query = db.query(YapePurchaseRequest).order_by(YapePurchaseRequest.created_at.desc())
    if filter == "pending":
        query = query.filter(YapePurchaseRequest.status == YapePurchaseStatus.PENDING)
    elif filter == "approved":
        query = query.filter(YapePurchaseRequest.status == YapePurchaseStatus.APPROVED)
    elif filter == "rejected":
        query = query.filter(YapePurchaseRequest.status == YapePurchaseStatus.REJECTED)

    purchases = query.limit(200).all()
    user_ids = {p.user_id for p in purchases}
    users = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids or {0})).all()}
    categories = {c.id: c for c in db.query(Category).all()}
    packages = {p["id"]: p for p in YAPE_PACKAGES}

    stats = {
        "pending": db.query(YapePurchaseRequest).filter(YapePurchaseRequest.status == YapePurchaseStatus.PENDING).count(),
        "approved": db.query(YapePurchaseRequest).filter(YapePurchaseRequest.status == YapePurchaseStatus.APPROVED).count(),
        "rejected": db.query(YapePurchaseRequest).filter(YapePurchaseRequest.status == YapePurchaseStatus.REJECTED).count(),
    }
    stats["total"] = stats["pending"] + stats["approved"] + stats["rejected"]

    return render(
        "admin/yape_purchases.html",
        {
            "purchases": purchases,
            "users": users,
            "categories": categories,
            "packages": packages,
            "filter": filter or "all",
            "stats": stats,
        },
        request=request,
        db=db,
        current_user=current_user,
    )


@router.post("/compras-yape/{purchase_id}/aprobar")
def approve_yape_purchase(
    purchase_id: int,
    filter: Optional[str] = Form(None),
    hp_granted: Optional[int] = Form(None),
    admin_notes: str = Form(""),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    purchase = db.get(YapePurchaseRequest, purchase_id)
    if not purchase:
        return _yape_redirect(filter, error="Solicitud+no+encontrada")
    if purchase.status != YapePurchaseStatus.PENDING:
        return _yape_redirect(filter, error="La+solicitud+ya+fue+revisada")

    granted = hp_granted if hp_granted is not None and hp_granted > 0 else purchase.hp_requested
    pkg = get_package(purchase.package_id)
    max_hp = (pkg["hp"] * 2) if pkg else purchase.hp_requested * 2
    if granted > max_hp:
        return _yape_redirect(filter, error="HP+otorgados+fuera+de+rango")

    purchase.status = YapePurchaseStatus.APPROVED
    purchase.hp_granted = granted
    purchase.reviewed_by_id = admin.id
    purchase.reviewed_at = peru_now()
    purchase.admin_notes = admin_notes.strip()[:255] or None
    db.commit()
    return _yape_redirect(filter, msg="Compra+aprobada")


@router.post("/compras-yape/{purchase_id}/rechazar")
def reject_yape_purchase(
    purchase_id: int,
    filter: Optional[str] = Form(None),
    admin_notes: str = Form(""),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    purchase = db.get(YapePurchaseRequest, purchase_id)
    if not purchase:
        return _yape_redirect(filter, error="Solicitud+no+encontrada")
    if purchase.status != YapePurchaseStatus.PENDING:
        return _yape_redirect(filter, error="La+solicitud+ya+fue+revisada")

    notes = admin_notes.strip()[:255]
    if not notes:
        return _yape_redirect(filter, error="Indica+el+motivo+del+rechazo")

    purchase.status = YapePurchaseStatus.REJECTED
    purchase.hp_granted = 0
    purchase.reviewed_by_id = admin.id
    purchase.reviewed_at = peru_now()
    purchase.admin_notes = notes
    db.commit()
    return _yape_redirect(filter, msg="Compra+rechazada")
