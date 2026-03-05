"""
core/database.py
────────────────
Central database module using SQLAlchemy ORM + SQLite.

Tables
------
- sessions        – conversation session state
- appointments    – available time-slots
- bookings        – customer bookings against slots
- chat_messages   – full conversation log (replaces JSONL)

Usage
-----
    from core.database import init_db, get_db

    init_db()                       # create tables (idempotent)
    with get_db() as db:            # scoped session
        db.add(...)
        db.commit()
"""

from __future__ import annotations

import os
import uuid
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Generator

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Float,
    Integer,
    String,
    Text,
    create_engine,
    event,
)
from sqlalchemy.orm import Session, declarative_base, sessionmaker

# ── Engine ───────────────────────────────────────────────────────────────
_DB_URL = os.getenv("DATABASE_URL", "sqlite:///data/civicflow.db")

engine = create_engine(
    _DB_URL,
    echo=False,
    connect_args={"check_same_thread": False} if "sqlite" in _DB_URL else {},
    pool_pre_ping=True,
)

# Enable WAL mode for SQLite (better concurrent reads)
if "sqlite" in _DB_URL:
    @event.listens_for(engine, "connect")
    def _set_sqlite_pragma(dbapi_conn, connection_record):  # noqa: ANN001
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA journal_mode=WAL")
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

SessionLocal = sessionmaker(bind=engine, autoflush=False, autocommit=False)
Base = declarative_base()


# ── Helpers ──────────────────────────────────────────────────────────────
def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


# ── Models ───────────────────────────────────────────────────────────────

class SessionModel(Base):
    """Tracks a user conversation session."""

    __tablename__ = "sessions"

    id = Column(String(64), primary_key=True, default=_new_id)
    name = Column(String(200), nullable=True)
    stage = Column(String(30), nullable=False, default="new")
    pending_intent = Column(String(50), nullable=True)
    pending_booking_phone = Column(String(20), nullable=True)
    pending_booking_service_type = Column(String(50), nullable=True)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<Session {self.id} stage={self.stage}>"


class AppointmentSlot(Base):
    """An available appointment time-slot."""

    __tablename__ = "appointment_slots"

    id = Column(Integer, primary_key=True, autoincrement=True)
    service_type = Column(String(50), nullable=False, index=True)
    slot_time = Column(DateTime(timezone=True), nullable=False)
    slot_label = Column(String(120), nullable=False, unique=True)
    is_active = Column(Boolean, default=True, nullable=False)

    def __repr__(self) -> str:
        return f"<Slot {self.slot_label}>"


class Booking(Base):
    """A customer booking against a slot."""

    __tablename__ = "bookings"

    id = Column(Integer, primary_key=True, autoincrement=True)
    booking_id = Column(String(30), unique=True, nullable=False, index=True)
    service_type = Column(String(50), nullable=False)
    customer_name = Column(String(200), nullable=False)
    customer_phone = Column(String(20), nullable=False, index=True)
    slot_label = Column(String(120), nullable=False)
    notes = Column(Text, default="")
    status = Column(String(20), nullable=False, default="booked")  # booked | cancelled
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    cancelled_at = Column(DateTime(timezone=True), nullable=True)

    def __repr__(self) -> str:
        return f"<Booking {self.booking_id} {self.status}>"


class ChatMessage(Base):
    """Stores every message exchanged in a session."""

    __tablename__ = "chat_messages"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String(64), nullable=False, index=True)
    role = Column(String(12), nullable=False)  # user | assistant | system
    content = Column(Text, nullable=False)
    intent = Column(String(50), nullable=True)
    refusal = Column(Boolean, default=False)
    best_similarity = Column(Float, nullable=True)
    sources_json = Column(Text, nullable=True)  # JSON string
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    def __repr__(self) -> str:
        return f"<ChatMessage {self.id} {self.role}>"


# ── Lifecycle ────────────────────────────────────────────────────────────

def init_db() -> None:
    """Create all tables (safe to call repeatedly)."""
    import pathlib

    # Ensure the data directory exists for SQLite
    if "sqlite" in _DB_URL:
        db_path = _DB_URL.replace("sqlite:///", "")
        pathlib.Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    Base.metadata.create_all(bind=engine)


@contextmanager
def get_db() -> Generator[Session, None, None]:
    """Yield a transactional DB session; auto-closes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def seed_default_slots() -> None:
    """Insert default appointment slots if the table is empty."""
    from datetime import timedelta

    with get_db() as db:
        if db.query(AppointmentSlot).count() > 0:
            return

        base = datetime(2026, 3, 5, tzinfo=timezone.utc)
        defaults = [
            ("dl_appointment", base.replace(hour=9, minute=0)),
            ("dl_appointment", base.replace(hour=10, minute=0)),
            ("dl_appointment", base.replace(hour=11, minute=0)),
            ("state_id", base.replace(hour=13, minute=30)),
            ("state_id", base.replace(hour=14, minute=30)),
            ("renewal", (base + timedelta(days=1)).replace(hour=9, minute=30)),
            ("renewal", (base + timedelta(days=1)).replace(hour=10, minute=30)),
        ]
        for svc, dt in defaults:
            label = f"{svc} | {dt.strftime('%Y-%m-%d %H:%M')}"
            db.add(AppointmentSlot(service_type=svc, slot_time=dt, slot_label=label))
        db.commit()
