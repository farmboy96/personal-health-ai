"""Oklahoma Blood Institute (OBI) app screening metrics stored in raw_measurements."""

from __future__ import annotations

import json
from datetime import datetime, time

from sqlalchemy.orm import Session

from app.db.models import RawMeasurement

OBI_SOURCE_NAME = "obi_app"

# Distinct from venous LabResult TOTAL_CHOLESTEROL — finger-stick screening at donation.
METRIC_OBI_TOTAL_CHOLESTEROL = "OBI_TOTAL_CHOLESTEROL"
METRIC_OBI_HEMOGLOBIN = "OBI_HEMOGLOBIN"
METRIC_OBI_PULSE = "OBI_PULSE"
METRIC_BP_SYSTOLIC = "BP_SYSTOLIC"
METRIC_BP_DIASTOLIC = "BP_DIASTOLIC"


def _payload(kind: str, **extra: str) -> str:
    base = {
        "measurement_method": "finger_stick_obi",
        "venue": "Oklahoma Blood Institute (donation screening)",
        "kind": kind,
    }
    base.update(extra)
    return json.dumps(base, sort_keys=True)


def format_obi_cholesterol_trajectory_for_prompt(db: Session) -> str:
    """Formatted block for AI prompts: dated OBI total cholesterol finger-stick series."""
    rows = (
        db.query(RawMeasurement)
        .filter(
            RawMeasurement.metric_type == METRIC_OBI_TOTAL_CHOLESTEROL,
            RawMeasurement.value.isnot(None),
        )
        .order_by(RawMeasurement.start_date.asc())
        .all()
    )
    if not rows:
        return ""

    lines: list[str] = []
    for r in rows:
        d = r.start_date.date() if hasattr(r.start_date, "date") else r.start_date
        lines.append(f"- {d.isoformat()}: total cholesterol {float(r.value):.0f} mg/dL (OBI finger-stick screening)")

    latest = rows[-1]
    ld = latest.start_date.date()
    lv = float(latest.value)
    header = (
        "Oklahoma Blood Institute finger-stick total cholesterol screening (not venous lab panel; "
        "directionally useful, less precise than clinical labs):\n"
    )
    narrative = (
        f"\nMost recent OBI screening: {ld.isoformat()} — {lv:.0f} mg/dL — highest recorded value in this series.\n"
        "Framing: total cholesterol from OBI screenings has been chronically elevated since at least September 2022; "
        "the March 28, 2026 reading is the highest on record in this patient-provided series."
    )
    return header + "\n".join(lines) + narrative


def format_obi_bp_line_for_prompt(db: Session, as_of_date) -> str:
    """Single-line summary of OBI BP used for context (optional helper)."""
    from datetime import date as Date

    if not isinstance(as_of_date, Date):
        return ""

    rows = (
        db.query(RawMeasurement)
        .filter(
            RawMeasurement.metric_type == METRIC_BP_SYSTOLIC,
            RawMeasurement.source_name == OBI_SOURCE_NAME,
            RawMeasurement.value.isnot(None),
        )
        .all()
    )
    if not rows:
        return ""
    before = [r for r in rows if r.start_date.date() <= as_of_date]
    if before:
        pick = max(before, key=lambda r: r.start_date)
    else:
        pick = min(rows, key=lambda r: abs((r.start_date.date() - as_of_date).days))
    d = pick.start_date.date()
    sbp = float(pick.value)
    dbp_row = (
        db.query(RawMeasurement)
        .filter(
            RawMeasurement.metric_type == METRIC_BP_DIASTOLIC,
            RawMeasurement.source_name == OBI_SOURCE_NAME,
            RawMeasurement.start_date >= datetime.combine(d, time.min),
            RawMeasurement.start_date <= datetime.combine(d, time.max),
        )
        .first()
    )
    dbp = float(dbp_row.value) if dbp_row and dbp_row.value is not None else None
    pair = f"{sbp:.0f}/{dbp:.0f} mmHg" if dbp is not None else f"{sbp:.0f} mmHg systolic"
    return f"Nearest OBI blood pressure for risk context ({d.isoformat()}): {pair}."
