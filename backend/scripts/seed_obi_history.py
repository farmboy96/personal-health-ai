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

import yaml
from sqlalchemy import text
from sqlalchemy.dialects.sqlite import insert

_BACKEND = Path(__file__).resolve().parents[1]
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

from app.db.database import SessionLocal, engine
from app.db.models import RawMeasurement, SourceFile

OBI_SOURCE_NAME = "obi_app"
SOURCE_FILENAME = "obi_app_screening_history_seed"
_SEED_PATH = _BACKEND / "data" / "seed" / "obi_history.yaml"


def _load_seed() -> dict:
    payload = yaml.safe_load(_SEED_PATH.read_text(encoding="utf-8")) or {}
    return dict(payload)


def _parse_date(raw: str) -> date:
    return date.fromisoformat(raw)


def _dt(d: date) -> datetime:
    return datetime.combine(d, time(12, 0, 0))


def _dedupe(metric_type: str, start: datetime, val_str: str, source_name: str) -> str:
    raw = f"{metric_type}|{start.isoformat()}|{val_str}|{source_name}"
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
        seed = _load_seed()
        obi_source_name = seed.get("obi_source_name", OBI_SOURCE_NAME)
        source_filename = seed.get("source_filename", SOURCE_FILENAME)
        hash_seed = seed.get("seed_content_hash_seed", "obi_history_seed_v1_robert")
        seed_content_hash = hashlib.sha256(str(hash_seed).encode("utf-8")).hexdigest()

        with engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL;"))
            conn.commit()

        sf = db.query(SourceFile).filter(SourceFile.file_hash == seed_content_hash).first()
        if not sf:
            sf = SourceFile(
                filename=source_filename,
                file_hash=seed_content_hash,
                file_type="obi_seed",
                stored_path=None,
                source_category=obi_source_name,
            )
            db.add(sf)
            db.commit()
            db.refresh(sf)

        rows_buffer: list[dict] = []

        for row in seed.get("bp_readings", []):
            d = _parse_date(row["date"])
            sys_v = int(row["systolic"])
            dia_v = int(row["diastolic"])
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
                        "source_name": obi_source_name,
                        "source_version": None,
                        "device": None,
                        "start_date": st,
                        "end_date": st,
                        "value": val,
                        "value_text": None,
                        "unit": unit,
                        "dedupe_hash": _dedupe(metric_type, st, str(val), obi_source_name),
                        "raw_payload": _payload(tag),
                    }
                )

        for row in seed.get("cholesterol_readings", []):
            d = _parse_date(row["date"])
            val = float(row["value"])
            st = _dt(d)
            metric_type = "OBI_TOTAL_CHOLESTEROL"
            rows_buffer.append(
                {
                    "source_file_id": sf.id,
                    "import_run_id": None,
                    "metric_type": metric_type,
                    "source_name": obi_source_name,
                    "source_version": None,
                    "device": None,
                    "start_date": st,
                    "end_date": st,
                    "value": val,
                    "value_text": None,
                    "unit": "mg/dL",
                    "dedupe_hash": _dedupe(metric_type, st, str(val), obi_source_name),
                    "raw_payload": _payload("total_cholesterol_screening"),
                }
            )

        for row in seed.get("hemoglobin_readings", []):
            d = _parse_date(row["date"])
            val = float(row["value"])
            st = _dt(d)
            metric_type = "OBI_HEMOGLOBIN"
            rows_buffer.append(
                {
                    "source_file_id": sf.id,
                    "import_run_id": None,
                    "metric_type": metric_type,
                    "source_name": obi_source_name,
                    "source_version": None,
                    "device": None,
                    "start_date": st,
                    "end_date": st,
                    "value": val,
                    "value_text": None,
                    "unit": "g/dL",
                    "dedupe_hash": _dedupe(metric_type, st, str(val), obi_source_name),
                    "raw_payload": _payload("hemoglobin_screening"),
                }
            )

        for row in seed.get("pulse_readings", []):
            d = _parse_date(row["date"])
            val = float(row["value"])
            st = _dt(d)
            metric_type = "OBI_PULSE"
            rows_buffer.append(
                {
                    "source_file_id": sf.id,
                    "import_run_id": None,
                    "metric_type": metric_type,
                    "source_name": obi_source_name,
                    "source_version": None,
                    "device": None,
                    "start_date": st,
                    "end_date": st,
                    "value": val,
                    "value_text": None,
                    "unit": "bpm",
                    "dedupe_hash": _dedupe(metric_type, st, str(val), obi_source_name),
                    "raw_payload": json.dumps(
                        {
                            "measurement_method": "finger_stick_obi",
                            "kind": "seated_pulse_at_donation",
                            "note": "Not true resting heart rate - seated pulse at donation visit.",
                        },
                        sort_keys=True,
                    ),
                }
            )

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

        from sqlalchemy import func

        q = (
            db.query(RawMeasurement.metric_type, func.count(RawMeasurement.id))
            .filter(RawMeasurement.source_name == obi_source_name)
            .group_by(RawMeasurement.metric_type)
            .all()
        )
        print(f"[counts by metric_type for source_name={obi_source_name}]")
        for mt, c in sorted(q):
            print(f"  {mt}: {c}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
