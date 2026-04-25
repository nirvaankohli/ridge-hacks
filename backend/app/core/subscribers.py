from __future__ import annotations

import sqlite3
import uuid
from datetime import UTC, datetime
from pathlib import Path


DB_PATH = Path(__file__).resolve().parents[2] / "solarsentinel.db"


def init_subscribers_db() -> None:
    with sqlite3.connect(DB_PATH) as connection:
        connection.execute(
            """
            CREATE TABLE IF NOT EXISTS subscribers (
                id TEXT PRIMARY KEY,
                phone TEXT NOT NULL,
                lat REAL NOT NULL,
                lon REAL NOT NULL,
                kp_threshold REAL NOT NULL,
                created_at TEXT NOT NULL
            )
            """
        )


def create_or_update_subscriber(phone: str, lat: float, lon: float, kp_threshold: float) -> dict:
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        existing = connection.execute(
            """
            SELECT * FROM subscribers
            WHERE phone = ? AND lat = ? AND lon = ? AND kp_threshold = ?
            """,
            (phone, lat, lon, kp_threshold),
        ).fetchone()
        if existing:
            return dict(existing)

        record = {
            "id": str(uuid.uuid4()),
            "phone": phone,
            "lat": lat,
            "lon": lon,
            "kp_threshold": kp_threshold,
            "created_at": datetime.now(UTC).isoformat(),
        }
        connection.execute(
            """
            INSERT INTO subscribers (id, phone, lat, lon, kp_threshold, created_at)
            VALUES (:id, :phone, :lat, :lon, :kp_threshold, :created_at)
            """,
            record,
        )
        return record


def list_subscribers() -> list[dict]:
    with sqlite3.connect(DB_PATH) as connection:
        connection.row_factory = sqlite3.Row
        rows = connection.execute(
            "SELECT id, phone, lat, lon, kp_threshold, created_at FROM subscribers ORDER BY created_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def delete_subscriber(subscriber_id: str) -> bool:
    with sqlite3.connect(DB_PATH) as connection:
        cursor = connection.execute("DELETE FROM subscribers WHERE id = ?", (subscriber_id,))
        return cursor.rowcount > 0


def mask_phone(phone: str) -> str:
    digits = "".join(char for char in phone if char.isdigit())
    if len(digits) <= 4:
        return digits
    return f"{'*' * (len(digits) - 4)}{digits[-4:]}"
