"""
core/appointments.py
────────────────────
Appointment booking engine backed by SQLAlchemy / SQLite.

The public interface (`AppointmentRequest`, `AppointmentStore`) is
unchanged so agent_graph.py and main.py keep working.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from .config import Settings
from .database import AppointmentSlot, Booking, get_db, _utcnow


@dataclass(frozen=True)
class AppointmentRequest:
    service_type: str
    customer_name: str
    customer_phone: str
    slot: str
    notes: str = ""


class AppointmentStore:
    def __init__(self, settings: Settings):
        # DB tables are created by init_db(); nothing file-based anymore.
        pass

    # ── queries ──────────────────────────────────────────────────────

    def list_open_slots(
        self, service_type: Optional[str] = None, limit: int = 10
    ) -> List[str]:
        with get_db() as db:
            q = db.query(AppointmentSlot).filter(AppointmentSlot.is_active == True)  # noqa: E712
            if service_type:
                q = q.filter(AppointmentSlot.service_type == service_type.lower().strip())

            all_slots = q.all()
            booked_labels = {
                b.slot_label
                for b in db.query(Booking).filter(Booking.status == "booked").all()
            }
            open_labels = [s.slot_label for s in all_slots if s.slot_label not in booked_labels]
            return open_labels[:limit]

    # ── mutations ────────────────────────────────────────────────────

    def create_booking(self, req: AppointmentRequest) -> Dict[str, Any]:
        with get_db() as db:
            slot = (
                db.query(AppointmentSlot)
                .filter(AppointmentSlot.slot_label == req.slot, AppointmentSlot.is_active == True)  # noqa: E712
                .first()
            )
            if not slot:
                raise ValueError("Requested slot is not available in schedule.")

            exists = (
                db.query(Booking)
                .filter(Booking.slot_label == req.slot, Booking.status == "booked")
                .first()
            )
            if exists:
                raise ValueError("Requested slot is already booked.")

            booking = Booking(
                booking_id=f"APT-{uuid.uuid4().hex[:10].upper()}",
                service_type=req.service_type,
                customer_name=req.customer_name,
                customer_phone=req.customer_phone,
                slot_label=req.slot,
                notes=req.notes or "",
                status="booked",
            )
            db.add(booking)
            db.commit()
            db.refresh(booking)

            return {
                "booking_id": booking.booking_id,
                "service_type": booking.service_type,
                "customer_name": booking.customer_name,
                "customer_phone": booking.customer_phone,
                "slot": booking.slot_label,
                "notes": booking.notes,
                "status": booking.status,
                "created_at": booking.created_at.isoformat() if booking.created_at else None,
            }

    def cancel_booking(self, booking_id: str) -> bool:
        with get_db() as db:
            b = (
                db.query(Booking)
                .filter(
                    Booking.booking_id == booking_id.upper(),
                    Booking.status == "booked",
                )
                .first()
            )
            if not b:
                return False
            b.status = "cancelled"
            b.cancelled_at = _utcnow()
            db.commit()
            return True

    def bookings_for_phone(self, phone: str) -> List[Dict[str, Any]]:
        p = _normalize_phone(phone)
        with get_db() as db:
            rows = (
                db.query(Booking)
                .filter(Booking.status == "booked")
                .all()
            )
            return [
                {
                    "booking_id": b.booking_id,
                    "service_type": b.service_type,
                    "slot": b.slot_label,
                    "customer_name": b.customer_name,
                }
                for b in rows
                if _normalize_phone(b.customer_phone) == p
            ]


def _normalize_phone(phone: str) -> str:
    return "".join(ch for ch in (phone or "") if ch.isdigit())
