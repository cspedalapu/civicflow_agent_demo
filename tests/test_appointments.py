from pathlib import Path

from core.appointments import AppointmentRequest, AppointmentStore
from core.config import Settings


def _settings(tmp_path: Path) -> Settings:
    return Settings(
        appointments_path=str(tmp_path / "appointments.json"),
    )


def test_create_and_cancel_booking(tmp_path: Path):
    store = AppointmentStore(_settings(tmp_path))
    slots = store.list_open_slots(limit=1)
    assert slots

    booking = store.create_booking(
        AppointmentRequest(
            service_type="dl_appointment",
            customer_name="Alice",
            customer_phone="5125551212",
            slot=slots[0],
        )
    )
    assert booking["status"] == "booked"

    ok = store.cancel_booking(booking["booking_id"])
    assert ok is True


def test_list_bookings_by_phone(tmp_path: Path):
    store = AppointmentStore(_settings(tmp_path))
    slot = store.list_open_slots(limit=1)[0]
    store.create_booking(
        AppointmentRequest(
            service_type="renewal",
            customer_name="Bob",
            customer_phone="(737) 555-1313",
            slot=slot,
        )
    )
    items = store.bookings_for_phone("7375551313")
    assert len(items) == 1
