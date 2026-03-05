"""
scripts/init_db.py
──────────────────
Initialise (or re-initialise) the SQLite database.

Usage:
    python -m scripts.init_db            # create tables + seed slots
    python -m scripts.init_db --reset    # drop all tables, recreate, reseed
"""

from __future__ import annotations

import sys

from dotenv import load_dotenv

load_dotenv()

from core.database import Base, engine, init_db, seed_default_slots  # noqa: E402


def main() -> None:
    reset = "--reset" in sys.argv

    if reset:
        print("⚠️  Dropping all tables …")
        Base.metadata.drop_all(bind=engine)

    print("Creating tables …")
    init_db()

    print("Seeding default appointment slots …")
    seed_default_slots()

    print("✅  Database ready.")


if __name__ == "__main__":
    main()
