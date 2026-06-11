import enum
from datetime import datetime, timedelta
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.timezone import peru_now

PREDICTIONS_CLOSE_MINUTES = 5


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    google_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    picture: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    phone_number: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    phone_verified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    referral_code: Mapped[Optional[str]] = mapped_column(String(12), unique=True, nullable=True, index=True)
    referred_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    predictions: Mapped[list["Prediction"]] = relationship("Prediction", back_populates="user")
    champion_predictions: Mapped[list["ChampionPrediction"]] = relationship(
        "ChampionPrediction", back_populates="user"
    )
    yape_purchases: Mapped[list["YapePurchaseRequest"]] = relationship(
        "YapePurchaseRequest",
        back_populates="user",
        foreign_keys="YapePurchaseRequest.user_id",
    )
    referred_by: Mapped[Optional["User"]] = relationship(
        "User", remote_side="User.id", foreign_keys=[referred_by_id]
    )


class AccountDeletion(Base):
    """Registro anonimizado de bajas (sin datos personales)."""

    __tablename__ = "account_deletions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    former_user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    email_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    registered_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    deleted_at: Mapped[datetime] = mapped_column(DateTime, default=peru_now, nullable=False, index=True)
    phone_verified: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    was_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    prediction_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    champion_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    deleted_by: Mapped[str] = mapped_column(String(20), default="self", nullable=False)


class PhoneVerification(Base):
    __tablename__ = "phone_verifications"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    phone_number: Mapped[str] = mapped_column(String(20), nullable=False)
    code_hash: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    uses_twilio: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    attempts: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)


class PredictionType(str, enum.Enum):
    SCORE = "score"
    DOUBLE_CHANCE = "double_chance"
    OVER_UNDER = "over_under"


class PredictionResult(str, enum.Enum):
    PENDING = "pending"
    HIT = "hit"
    MISS = "miss"


class Category(Base):
    """Torneo / competencia de fútbol."""
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    season: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    starts_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    champion_closes_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    champion_team: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)

    matches: Mapped[list["Match"]] = relationship(
        "Match", back_populates="category", cascade="all, delete-orphan"
    )
    champion_predictions: Mapped[list["ChampionPrediction"]] = relationship(
        "ChampionPrediction", back_populates="category", cascade="all, delete-orphan"
    )

    @property
    def champion_decided(self) -> bool:
        return bool(self.champion_team)


class Match(Base):
    __tablename__ = "matches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False)
    home_team: Mapped[str] = mapped_column(String(100), nullable=False)
    away_team: Mapped[str] = mapped_column(String(100), nullable=False)
    match_date: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    group_name: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    venue: Mapped[Optional[str]] = mapped_column(String(150), nullable=True)
    home_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    away_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    category: Mapped["Category"] = relationship("Category", back_populates="matches")
    predictions: Mapped[list["Prediction"]] = relationship(
        "Prediction", back_populates="match", cascade="all, delete-orphan"
    )

    @property
    def is_finished(self) -> bool:
        return self.home_score is not None and self.away_score is not None

    @property
    def total_goals(self) -> Optional[int]:
        if not self.is_finished:
            return None
        return self.home_score + self.away_score

    @property
    def predictions_open(self) -> bool:
        if self.is_finished:
            return False
        cutoff = self.match_date - timedelta(minutes=PREDICTIONS_CLOSE_MINUTES)
        return peru_now() < cutoff

    @property
    def predictions_status(self) -> str:
        if self.is_finished:
            return "finished"
        if not self.predictions_open:
            return "closed"
        return "open"


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    type: Mapped[PredictionType] = mapped_column(Enum(PredictionType), nullable=False)
    predicted_home_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    predicted_away_score: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    double_chance: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    over_under_line: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    over_under_pick: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    result: Mapped[PredictionResult] = mapped_column(
        Enum(PredictionResult), default=PredictionResult.PENDING, nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    match: Mapped["Match"] = relationship("Match", back_populates="predictions")
    user: Mapped[Optional["User"]] = relationship("User", back_populates="predictions")


class ChampionPrediction(Base):
    __tablename__ = "champion_predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False, index=True)
    champion_team: Mapped[str] = mapped_column(String(100), nullable=False)
    result: Mapped[PredictionResult] = mapped_column(
        Enum(PredictionResult), default=PredictionResult.PENDING, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    user: Mapped["User"] = relationship("User", back_populates="champion_predictions")
    category: Mapped["Category"] = relationship("Category", back_populates="champion_predictions")


class YapePurchaseStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class YapePurchaseRequest(Base):
    """Solicitud de compra vía Yape (verificación admin)."""

    __tablename__ = "yape_purchase_requests"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id"), nullable=True, index=True)
    package_id: Mapped[str] = mapped_column(String(20), nullable=False)
    amount_soles: Mapped[int] = mapped_column(Integer, nullable=False)
    hp_requested: Mapped[int] = mapped_column(Integer, nullable=False)
    hp_granted: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    operation_code: Mapped[str] = mapped_column(String(20), unique=True, nullable=False, index=True)
    user_note: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[YapePurchaseStatus] = mapped_column(
        Enum(YapePurchaseStatus), default=YapePurchaseStatus.PENDING, nullable=False, index=True
    )
    admin_notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    reviewed_by_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=peru_now, nullable=False, index=True)

    user: Mapped["User"] = relationship("User", foreign_keys=[user_id], back_populates="yape_purchases")
    category: Mapped[Optional["Category"]] = relationship("Category")
    reviewed_by: Mapped[Optional["User"]] = relationship("User", foreign_keys=[reviewed_by_id])


class PointsRule(Base):
    """HP configurables por torneo (category_id=null → valores globales por defecto)."""

    __tablename__ = "points_rules"
    __table_args__ = (
        UniqueConstraint("category_id", "rule_key", name="uq_points_rules_category_key"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    category_id: Mapped[Optional[int]] = mapped_column(ForeignKey("categories.id"), nullable=True, index=True)
    rule_key: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    hp_value: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=peru_now, nullable=False)

    category: Mapped[Optional["Category"]] = relationship("Category")


class PointBonusType(str, enum.Enum):
    REFERRAL_REFERRER = "referral_referrer"
    REFERRAL_REFERRED = "referral_referred"
    GROUP_LEADER = "group_leader"


class PointBonus(Base):
    """Bonificaciones de HP (referidos, líder de grupo, etc.)."""

    __tablename__ = "point_bonuses"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "category_id", "bonus_type", "reference_key",
            name="uq_point_bonuses_user_cat_type_ref",
        ),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False, index=True)
    category_id: Mapped[int] = mapped_column(ForeignKey("categories.id"), nullable=False, index=True)
    bonus_type: Mapped[PointBonusType] = mapped_column(Enum(PointBonusType), nullable=False, index=True)
    hp: Mapped[int] = mapped_column(Integer, nullable=False)
    reference_key: Mapped[str] = mapped_column(String(80), nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=peru_now, nullable=False)

    user: Mapped["User"] = relationship("User")
    category: Mapped["Category"] = relationship("Category")
