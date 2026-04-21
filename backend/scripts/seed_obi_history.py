"""
Idempotent seed of Oklahoma Blood Institute (OBI) app screening history into raw_measurements.

Source: patient-provided dates/values. category/source_name: obi_app.

Run from repo root:
  backend\\.venv\\Scripts\\python.exe backend\\scripts\\seed_obi_history.py
"""

from __future__ import annotations

import hashlib
import json
import sys
from datetime import date, datetime, time
from pathlib import Path

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from sqlalchemy.dialects.sqlite import insert

from app.db.database import SessionLocal, engine
from app.db.models import RawMeasurement, SourceFile
from sqlalchemy import text

OBI_SOURCE_NAME = "obi_app"
SOURCE_FILENAME = "obi_app_screening_history_seed"
# Stable pseudo-file identity for idempotent SourceFile row
SEED_CONTENT_HASH = hashlib.sha256(b"obi_history_seed_v1_robert").hexdigest()

BP_READINGS: list[tuple[date, int, int]] = [
    (date(2026, 3, 28), 118, 75),
    (date(2025, 7, 2), 122, 73),
    (date(2024, 11, 30), 123, 79),
    (date(2024, 7, 5), 116, 77),
    (date(2024, 5, 10), 99, 67),
    (date(2024, 2, 23), 118, 72),
    (date(2023, 12, 16), 126, 77),
    (date(2023, 10, 21), 117, 78),
    (date(2023, 8, 19), 130, 74),
    (date(2023, 6, 24), 117, 78),
    (date(2023, 4, 22), 135, 70),
    (date(2022, 12, 31), 122, 77),
    (date(2022, 9, 17), 122, 70),
]

CHOLESTEROL_READINGS: list[tuple[date, int]] = [
    (date(2026, 3, 28), 311),
    (date(2025, 7, 2), 232),
    (date(2024, 11, 30), 220),
    (date(2024, 5, 10), 198),
    (date(2024, 2, 23), 248),
    (date(2023, 12, 16), 215),
    (date(2023, 10, 21), 238),
    (date(2023, 8, 19), 262),
    (date(2023, 6, 24), 246),
    (date(2023, 4, 22), 209),
    (date(2022, 12, 31), 231),
    (date(2022, 9, 17), 251),
]

HEMOGLOBIN_READINGS: list[tuple[date, float]] = [
    (date(2026, 3, 28), 19.0),
    (date(2025, 7, 2), 18.3),
    (date(2024, 11, 30), 17.6),
]

PULSE_READINGS: list[tuple[date, int]] = [
    (date(2026, 3, 28), 73),
    (date(2025, 7, 2), 80),
    (date(2024, 11, 30), 75),
]


def _dt(d: date) -> datetime:
    return datetime.combine(d, time(12, 0, 0))


def _dedupe(metric_type: str, start: datetime, val_str: str) -> str:
    raw = f"{metric_type}|{start.isoformat()}|{val_str}|{OBI_SOURCE_NAME}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def _payload(kind: str) -> str:
    return json.dumps(
        {
            "measurement_method": "finger_stick_obi",
            "venue": "Oklahoma Blood Institute",
            "kind": kind,
            "note": "Screening-grade; less precise than venous clinical labs.",
        },
        sort_keys=True,
    )


def main() -> None:
    db = SessionLocal()
    try:
        with engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL;"))
            conn.commit()

        sf = db.query(SourceFile).filter(SourceFile.file_hash == SEED_CONTENT_HASH).first()
        if not sf:
            sf = SourceFile(
                filename=SOURCE_FILENAME,
                file_hash=SEED_CONTENT_HASH,
                file_type="obi_seed",
                stored_path=None,
                source_category=OBI_SOURCE_NAME,
            )
            db.add(sf)
            db.commit()
            db.refresh(sf)

        rows_buffer: list[dict] = []

        # BP
        for d, sys_v, dia_v in BP_READINGS:
            st = _dt(d)
            for metric_type, val, unit, tag in (
                ("BP_SYSTOLIC", float(sys_v), "mmHg", "bp_systolic"),
                ("BP_DIASTOLIC", float(dia_v), "mmHg", "bp_diastolic"),
            ):
                rows_buffer.append(
                    {
                        "source_file_id": sf.id,
                        "import_run_id": None,
                        "metric_type": metric_type,
                        "source_name": OBI_SOURCE_NAME,
                        "source_version": None,
                        "device": None,
                        "start_date": st,
                        "end_date": st,
                        "value": val,
                        "value_text": None,
                        "unit": unit,
                        "dedupe_hash": _dedupe(metric_type, st, str(val)),
                        "raw_payload": _payload(tag),
                    }
                )

        for d, tc in CHOLESTEROL_READINGS:
            st = _dt(d)
            metric_type = "OBI_TOTAL_CHOLESTEROL"
            val = float(tc)
            rows_buffer.append(
                {
                    "source_file_id": sf.id,
                    "import_run_id": None,
                    "metric_type": metric_type,
                    "source_name": OBI_SOURCE_NAME,
                    "source_version": None,
                    "device": None,
                    "start_date": st,
                    "end_date": st,
                    "value": val,
                    "value_text": None,
                    "unit": "mg/dL",
                    "dedupe_hash": _dedupe(metric_type, st, str(val)),
                    "raw_payload": _payload("total_cholesterol_screening"),
                }
            )

        for d, hb in HEMOGLOBIN_READINGS:
            st = _dt(d)
            metric_type = "OBI_HEMOGLOBIN"
            val = float(hb)
            rows_buffer.append(
                {
                    "source_file_id": sf.id,
                    "import_run_id": None,
                    "metric_type": metric_type,
                    "source_name": OBI_SOURCE_NAME,
                    "source_version": None,
                    "device": None,
                    "start_date": st,
                    "end_date": st,
                    "value": val,
                    "value_text": None,
                    "unit": "g/dL",
                    "dedupe_hash": _dedupe(metric_type, st, str(val)),
                    "raw_payload": _payload("hemoglobin_screening"),
                }
            )

        for d, pulse in PULSE_READINGS:
            st = _dt(d)
            metric_type = "OBI_PULSE"
            val = float(pulse)
            rows_buffer.append(
                {
                    "source_file_id": sf.id,
                    "import_run_id": None,
                    "metric_type": metric_type,
                    "source_name": OBI_SOURCE_NAME,
                    "source_version": None,
                    "device": None,
                    "start_date": st,
                    "end_date": st,
                    "value": val,
                    "value_text": None,
                    "unit": "bpm",
                    "dedupe_hash": _dedupe(metric_type, st, str(val)),
                    "raw_payload": json.dumps(
                        {
                            "measurement_method": "finger_stick_obi",
                            "kind": "seated_pulse_at_donation",
                            "note": "Not true resting heart rate — seated pulse at donation visit.",
                        },
                        sort_keys=True,
                    ),
                }
            )

        # Insert with accurate counts (rowcount per batch unreliable for sqlite sometimes)
        inserted_total = 0
        chunk_size = 80
        for i in range(0, len(rows_buffer), chunk_size):
            chunk = rows_buffer[i : i + chunk_size]
            stmt = insert(RawMeasurement).values(chunk)
            stmt = stmt.on_conflict_do_nothing(index_elements=["dedupe_hash"])
            res = db.execute(stmt)
            inserted_total += res.rowcount or 0
            db.commit()

        print(f"[done] Insert attempts: {len(rows_buffer)}, rows reported inserted (new): {inserted_total}")

        # Per-metric counts in DB for OBI source
        from sqlalchemy import func

        q = (
            db.query(RawMeasurement.metric_type, func.count(RawMeasurement.id))
            .filter(RawMeasurement.source_name == OBI_SOURCE_NAME)
            .group_by(RawMeasurement.metric_type)
            .all()
        )
        print("[counts by metric_type for source_name=obi_app]")
        for mt, c in sorted(q):
            print(f"  {mt}: {c}")

    finally:
        db.close()


if __name__ == "__main__":
    main()
