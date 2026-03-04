from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import json
import threading
import uuid

from .config import Settings

_LOCK = threading.RLock()


@dataclass(frozen=True)
class AppointmentRequest:
    service_type: str
    customer_name: str
    customer_phone: str
    slot: str
    notes: str = ""


class AppointmentStore:
    def __init__(self, settings: Settings):
        self.path = Path(settings.appointments_path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        if not self.path.exists():
            self._write(
                {
                    "slots": _default_slots(),
                    "bookings": [],
                }
            )

    def _read(self) -> Dict[str, Any]:
        with _LOCK:
            if not self.path.exists():
                return {"slots": _default_slots(), "bookings": []}
            return json.loads(self.path.read_text(encoding="utf-8"))

    def _write(self, obj: Dict[str, Any]) -> None:
        with _LOCK:
            self.path.write_text(json.dumps(obj, ensure_ascii=False, indent=2), encoding="utf-8")

    def list_open_slots(self, service_type: Optional[str] = None, limit: int = 10) -> List[str]:
        data = self._read()
        slots = data.get("slots", [])
        bookings = data.get("bookings", [])
        booked = {b["slot"] for b in bookings if b.get("status") == "booked"}
        open_slots = [s for s in slots if s not in booked]
        if service_type:
            token = service_type.lower().strip()
            open_slots = [s for s in open_slots if token in s.lower()]
        return open_slots[:limit]

    def create_booking(self, req: AppointmentRequest) -> Dict[str, Any]:
        data = self._read()
        slots = data.get("slots", [])
        bookings = data.get("bookings", [])
        if req.slot not in slots:
            raise ValueError("Requested slot is not available in schedule.")
        if any(b.get("slot") == req.slot and b.get("status") == "booked" for b in bookings):
            raise ValueError("Requested slot is already booked.")

        booking = {
            "booking_id": f"APT-{uuid.uuid4().hex[:10].upper()}",
            "service_type": req.service_type,
            "customer_name": req.customer_name,
            "customer_phone": req.customer_phone,
            "slot": req.slot,
            "notes": req.notes,
            "status": "booked",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        bookings.append(booking)
        data["bookings"] = bookings
        self._write(data)
        return booking

    def cancel_booking(self, booking_id: str) -> bool:
        data = self._read()
        found = False
        for b in data.get("bookings", []):
            if b.get("booking_id", "").lower() == booking_id.lower() and b.get("status") == "booked":
                b["status"] = "cancelled"
                b["cancelled_at"] = datetime.now(timezone.utc).isoformat()
                found = True
                break
        if found:
            self._write(data)
        return found

    def bookings_for_phone(self, phone: str) -> List[Dict[str, Any]]:
        p = _normalize_phone(phone)
        data = self._read()
        return [
            b
            for b in data.get("bookings", [])
            if _normalize_phone(b.get("customer_phone", "")) == p and b.get("status") == "booked"
        ]


def _normalize_phone(phone: str) -> str:
    return "".join(ch for ch in (phone or "") if ch.isdigit())


def _default_slots() -> List[str]:
    return [
        "dl_appointment | 2026-03-05 09:00",
        "dl_appointment | 2026-03-05 10:00",
        "dl_appointment | 2026-03-05 11:00",
        "state_id | 2026-03-05 13:30",
        "state_id | 2026-03-05 14:30",
        "renewal | 2026-03-06 09:30",
        "renewal | 2026-03-06 10:30",
    ]
