from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime, timezone
from .db import Base


class Deck(Base):
    __tablename__ = "decks"

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String, nullable=False)
    description = Column(Text, default="")
    category = Column(String, default="")
    favorite = Column(Integer, default=0)
    hidden = Column(Integer, default=0)
    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    cards = relationship("Card", back_populates="deck", cascade="all, delete-orphan")


class Card(Base):
    __tablename__ = "cards"

    id = Column(Integer, primary_key=True, autoincrement=True)
    deck_id = Column(Integer, ForeignKey("decks.id"), nullable=False)
    front = Column(Text, nullable=False)
    back = Column(Text, nullable=False)
    media_files = Column(Text, default="")

    card_type = Column(Integer, default=0)
    queue = Column(Integer, default=0)
    due = Column(Integer, default=0)
    interval = Column(Integer, default=0)
    ease_factor = Column(Float, default=2.5)
    reps = Column(Integer, default=0)
    lapses = Column(Integer, default=0)
    left = Column(Integer, default=0)

    created_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at = Column(DateTime, default=lambda: datetime.now(timezone.utc), onupdate=lambda: datetime.now(timezone.utc))

    deck = relationship("Deck", back_populates="cards")
    reviews = relationship("ReviewLog", back_populates="card", cascade="all, delete-orphan")


class ReviewLog(Base):
    __tablename__ = "review_log"

    id = Column(Integer, primary_key=True, autoincrement=True)
    card_id = Column(Integer, ForeignKey("cards.id"), nullable=False)
    ease = Column(Integer, nullable=False)
    interval = Column(Integer, nullable=False)
    last_interval = Column(Integer, nullable=False)
    ease_factor = Column(Float, nullable=False)
    time_ms = Column(Integer, default=0)
    review_type = Column(Integer, default=0)
    reviewed_at = Column(DateTime, default=lambda: datetime.now(timezone.utc))

    card = relationship("Card", back_populates="reviews")
