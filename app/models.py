import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    google_id: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    picture: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    is_admin: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, nullable=False)

    predictions: Mapped[list["Prediction"]] = relationship("Prediction", back_populates="user")


class PredictionType(str, enum.Enum):
    DOUBLE_CHANCE = "double_chance"
    OVER_UNDER = "over_under"


class PredictionResult(str, enum.Enum):
    PENDING = "pending"
    HIT = "hit"
    MISS = "miss"


class Category(Base):
    __tablename__ = "categories"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)

    matches: Mapped[list["Match"]] = relationship(
        "Match", back_populates="category", cascade="all, delete-orphan"
    )


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


class Prediction(Base):
    __tablename__ = "predictions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    match_id: Mapped[int] = mapped_column(ForeignKey("matches.id"), nullable=False)
    user_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    type: Mapped[PredictionType] = mapped_column(Enum(PredictionType), nullable=False)
    double_chance: Mapped[Optional[str]] = mapped_column(String(5), nullable=True)
    over_under_line: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    over_under_pick: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    result: Mapped[PredictionResult] = mapped_column(
        Enum(PredictionResult), default=PredictionResult.PENDING, nullable=False
    )
    notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    match: Mapped["Match"] = relationship("Match", back_populates="predictions")
    user: Mapped[Optional["User"]] = relationship("User", back_populates="predictions")
