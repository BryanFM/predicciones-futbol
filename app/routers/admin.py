from typing import Optional

from datetime import datetime

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse, RedirectResponse
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.auth import require_admin
from app.database import get_db
from app.models import Category, ChampionPrediction, PhoneVerification, Prediction, User, AccountDeletion, YapePurchaseRequest, YapePurchaseStatus
from app.points import user_hamster_points
from app.rendering import render
from app.timezone import peru_now
from app.yape_admin import approve_purchase, register_and_approve_purchase, validate_hp_grant
from app.yape_policy import YAPE_PACKAGES

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

    yape_hp_by_user: dict[int, int] = {}
    for u in users:
        pts = user_hamster_points(db, u.id, selected_category_id)
        yape_hp_by_user[u.id] = pts["purchased_points"]

    from app.referrals import admin_users_referral_maps

    referral_maps = admin_users_referral_maps(db, users)

    total = db.query(User).count()
    verified = db.query(User).filter(User.phone_verified.is_(True)).count()
    deleted_total = db.query(AccountDeletion).count()

    return render(
        "admin/users.html",
        {
            "users": users,
            "pred_counts": pred_counts,
            "champion_by_user": champion_by_user,
            "yape_hp_by_user": yape_hp_by_user,
            "referrers": referral_maps["referrers"],
            "invited_total": referral_maps["invited_total"],
            "invited_verified": referral_maps["invited_verified"],
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
    user_id: Optional[int] = None,
    msg: Optional[str] = None,
    error: Optional[str] = None,
) -> RedirectResponse:
    params = []
    if filter and filter != "all":
        params.append(f"filter={filter}")
    if user_id:
        params.append(f"user_id={user_id}")
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
    user_id: Optional[int] = None,
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
    if user_id:
        query = query.filter(YapePurchaseRequest.user_id == user_id)

    purchases = query.limit(200).all()
    user_ids = {p.user_id for p in purchases}
    if user_id:
        user_ids.add(user_id)
    users = {u.id: u for u in db.query(User).filter(User.id.in_(user_ids or {0})).all()}
    categories = db.query(Category).filter(Category.is_active.is_(True)).order_by(Category.name).all()
    all_categories = {c.id: c for c in db.query(Category).all()}
    packages = {p["id"]: p for p in YAPE_PACKAGES}
    verified_users = (
        db.query(User)
        .filter(User.phone_verified.is_(True))
        .order_by(User.name)
        .all()
    )
    filter_user = users.get(user_id) if user_id else None

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
            "all_categories": all_categories,
            "packages": packages,
            "package_list": YAPE_PACKAGES,
            "verified_users": verified_users,
            "filter": filter or "all",
            "filter_user_id": user_id,
            "filter_user": filter_user,
            "stats": stats,
        },
        request=request,
        db=db,
        current_user=current_user,
    )


@router.post("/compras-yape/registrar")
def register_yape_purchase(
    user_id: int = Form(...),
    category_id: int = Form(...),
    package_id: str = Form(...),
    operation_code: str = Form(...),
    hp_granted: Optional[int] = Form(None),
    user_note: str = Form(""),
    admin_notes: str = Form(""),
    filter: Optional[str] = Form(None),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    _, err = register_and_approve_purchase(
        db,
        admin=admin,
        user_id=user_id,
        category_id=category_id,
        package_id=package_id,
        operation_code=operation_code,
        hp_granted=hp_granted,
        user_note=user_note,
        admin_notes=admin_notes,
    )
    if err:
        return _yape_redirect(filter, user_id, error=err.replace(" ", "+"))
    return _yape_redirect(filter, user_id, msg="Pago+registrado+y+HP+acreditados")


@router.post("/compras-yape/{purchase_id}/aprobar")
def approve_yape_purchase(
    purchase_id: int,
    filter: Optional[str] = Form(None),
    user_id: Optional[int] = Form(None),
    hp_granted: Optional[int] = Form(None),
    admin_notes: str = Form(""),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    purchase = db.get(YapePurchaseRequest, purchase_id)
    if not purchase:
        return _yape_redirect(filter, user_id, error="Solicitud+no+encontrada")
    if purchase.status != YapePurchaseStatus.PENDING:
        return _yape_redirect(filter, user_id, error="La+solicitud+ya+fue+revisada")

    granted = hp_granted if hp_granted is not None and hp_granted > 0 else purchase.hp_requested
    err = approve_purchase(db, purchase, admin, granted, admin_notes)
    if err:
        return _yape_redirect(filter, user_id, error=err.replace(" ", "+"))
    return _yape_redirect(filter, user_id, msg=f"Compra+aprobada:+{granted}+HP")


@router.post("/compras-yape/{purchase_id}/ajustar-hp")
def adjust_yape_hp(
    purchase_id: int,
    filter: Optional[str] = Form(None),
    user_id: Optional[int] = Form(None),
    hp_granted: int = Form(...),
    admin_notes: str = Form(""),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    purchase = db.get(YapePurchaseRequest, purchase_id)
    if not purchase:
        return _yape_redirect(filter, user_id, error="Solicitud+no+encontrada")
    if purchase.status != YapePurchaseStatus.APPROVED:
        return _yape_redirect(filter, user_id, error="Solo+se+pueden+ajustar+compras+aprobadas")

    err = validate_hp_grant(purchase.package_id, purchase.hp_requested, hp_granted)
    if err:
        return _yape_redirect(filter, user_id, error=err.replace(" ", "+"))

    purchase.hp_granted = hp_granted
    note = admin_notes.strip()[:255]
    if note:
        purchase.admin_notes = note
    purchase.reviewed_by_id = admin.id
    purchase.reviewed_at = peru_now()
    db.commit()
    return _yape_redirect(filter, user_id, msg=f"HP+actualizados+a+{hp_granted}")


@router.post("/compras-yape/{purchase_id}/rechazar")
def reject_yape_purchase(
    purchase_id: int,
    filter: Optional[str] = Form(None),
    user_id: Optional[int] = Form(None),
    admin_notes: str = Form(""),
    db: Session = Depends(get_db),
    admin: User = Depends(require_admin),
):
    purchase = db.get(YapePurchaseRequest, purchase_id)
    if not purchase:
        return _yape_redirect(filter, user_id, error="Solicitud+no+encontrada")
    if purchase.status != YapePurchaseStatus.PENDING:
        return _yape_redirect(filter, user_id, error="La+solicitud+ya+fue+revisada")

    notes = admin_notes.strip()[:255]
    if not notes:
        return _yape_redirect(filter, user_id, error="Indica+el+motivo+del+rechazo")

    purchase.status = YapePurchaseStatus.REJECTED
    purchase.hp_granted = 0
    purchase.reviewed_by_id = admin.id
    purchase.reviewed_at = peru_now()
    purchase.admin_notes = notes
    db.commit()
    return _yape_redirect(filter, user_id, msg="Compra+rechazada")


def _points_redirect(
    category_id: Optional[int] = None,
    msg: Optional[str] = None,
    error: Optional[str] = None,
) -> RedirectResponse:
    params = []
    if category_id:
        params.append(f"category_id={category_id}")
    if msg:
        params.append(f"msg={msg}")
    if error:
        params.append(f"error={error}")
    qs = "&".join(params)
    return RedirectResponse(f"/admin/puntos{'?' + qs if qs else ''}", status_code=303)


@router.get("/puntos", response_class=HTMLResponse)
def points_settings(
    request: Request,
    category_id: Optional[int] = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_admin),
):
    from app.models import PointBonus, User as UserModel
    from app.points_rules import get_rules_for_admin, seed_default_rules

    seed_default_rules(db)
    categories = db.query(Category).order_by(Category.name).all()
    selected = category_id if category_id is not None else None
    rules = get_rules_for_admin(db, selected)

    referrals = (
        db.query(UserModel)
        .filter(UserModel.referred_by_id.isnot(None))
        .order_by(UserModel.created_at.desc())
        .limit(50)
        .all()
    )
    referrers = {u.id: u for u in db.query(UserModel).filter(UserModel.id.in_({r.referred_by_id for r in referrals} or {0})).all()}
    recent_bonuses = (
        db.query(PointBonus)
        .order_by(PointBonus.created_at.desc())
        .limit(30)
        .all()
    )
    bonus_users = {u.id: u for u in db.query(UserModel).filter(UserModel.id.in_({b.user_id for b in recent_bonuses} or {0})).all()}

    return render(
        "admin/points.html",
        {
            "categories": categories,
            "selected_category_id": selected,
            "rules": rules,
            "referrals": referrals,
            "referrers": referrers,
            "recent_bonuses": recent_bonuses,
            "bonus_users": bonus_users,
        },
        request=request,
        db=db,
        current_user=current_user,
    )


@router.post("/puntos")
def save_points_settings(
    rule_key: str = Form(...),
    hp_value: int = Form(...),
    category_id: Optional[int] = Form(None),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    from app.points_rules import save_rule_hp

    cat_id = category_id if category_id else None
    try:
        save_rule_hp(db, rule_key, hp_value, cat_id)
    except ValueError as exc:
        return _points_redirect(cat_id, error=str(exc).replace(" ", "+"))
    return _points_redirect(cat_id, msg="Regla+actualizada")


@router.post("/puntos/recalcular-lideres")
def recalc_group_leaders(
    category_id: int = Form(...),
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    from app.group_leader import evaluate_group_leaders

    created = evaluate_group_leaders(db, category_id)
    return _points_redirect(category_id, msg=f"Lideres+de+grupo:+{created}+bonos+nuevos")
