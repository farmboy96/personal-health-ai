"""
Apple Health rolling aggregates (30/90/365-day windows) for daily summary / AI context.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import RawMeasurement

METRICS_TO_ROLL: dict[str, tuple[str, str, str]] = {
    "resting_heart_rate": (
        "HKQuantityTypeIdentifierRestingHeartRate",
        "mean",
        "bpm",
    ),
    "hrv_sdnn": (
        "HKQuantityTypeIdentifierHeartRateVariabilitySDNN",
        "mean",
        "ms",
    ),
    "vo2_max": ("HKQuantityTypeIdentifierVO2Max", "mean", "ml/kg/min"),
    "steps_daily": (
        "HKQuantityTypeIdentifierStepCount",
        "daily_sum_then_mean",
        "steps/day",
    ),
    "active_energy_daily": (
        "HKQuantityTypeIdentifierActiveEnergyBurned",
        "daily_sum_then_mean",
        "kcal/day",
    ),
    "exercise_minutes_daily": (
        "HKQuantityTypeIdentifierAppleExerciseTime",
        "daily_sum_then_mean",
        "min/day",
    ),
    "body_mass": ("HKQuantityTypeIdentifierBodyMass", "mean", "lb"),
    "body_fat_pct": (
        "HKQuantityTypeIdentifierBodyFatPercentage",
        "mean",
        "%",
    ),
    "sleep_hours_daily": (
        "HKCategoryTypeIdentifierSleepAnalysis",
        "sleep_duration_hours",
        "hrs/night",
    ),
}


def _end_of_day(d: date) -> datetime:
    return datetime.combine(d, time.max)


def _window_start_dt(today: date, days: int) -> datetime:
    return datetime.combine(today - timedelta(days=days), time.min)


def _sql_mean(
    db: Session,
    metric_type: str,
    window_start: datetime,
    window_end: datetime,
) -> float | None:
    q = (
        db.query(func.avg(RawMeasurement.value))
        .filter(
            RawMeasurement.metric_type == metric_type,
            RawMeasurement.start_date >= window_start,
            RawMeasurement.start_date <= window_end,
            RawMeasurement.value.isnot(None),
        )
        .scalar()
    )
    if q is None:
        return None
    return float(q)


def _daily_sum_then_mean(
    db: Session,
    metric_type: str,
    window_start: datetime,
    window_end: datetime,
) -> float | None:
    day_col = func.date(RawMeasurement.start_date)
    rows = (
        db.query(day_col, func.sum(RawMeasurement.value))
        .filter(
            RawMeasurement.metric_type == metric_type,
            RawMeasurement.start_date >= window_start,
            RawMeasurement.start_date <= window_end,
            RawMeasurement.value.isnot(None),
        )
        .group_by(day_col)
        .all()
    )
    if not rows:
        return None
    daily_sums = [float(r[1]) for r in rows if r[1] is not None]
    if not daily_sums:
        return None
    return sum(daily_sums) / len(daily_sums)


def _build_sleep_daily_hours(
    db: Session,
    window_start: datetime,
    window_end: datetime,
) -> dict[date, float]:
    rows = (
        db.query(
            RawMeasurement.start_date,
            RawMeasurement.end_date,
            RawMeasurement.value,
            RawMeasurement.value_text,
        )
        .filter(
            RawMeasurement.metric_type == "HKCategoryTypeIdentifierSleepAnalysis",
            RawMeasurement.start_date >= window_start,
            RawMeasurement.start_date <= window_end,
        )
        .all()
    )
    daily: dict[date, float] = defaultdict(float)
    for r in rows:
        if r.value is not None and float(r.value) == 0.0:
            continue
        if r.value_text and "Asleep" not in r.value_text:
            continue
        if not r.end_date or not r.start_date:
            continue
        hrs = (r.end_date - r.start_date).total_seconds() / 3600.0
        if hrs <= 0:
            continue
        d0 = r.start_date.date() if hasattr(r.start_date, "date") else r.start_date
        if isinstance(d0, datetime):
            d0 = d0.date()
        daily[d0] += hrs
    return dict(daily)


def _mean_sleep_for_window(
    daily: dict[date, float], today: date, window_days: int
) -> float | None:
    cutoff = today - timedelta(days=window_days)
    vals = [v for d, v in daily.items() if cutoff <= d <= today]
    if not vals:
        return None
    return sum(vals) / len(vals)


def compute_rollups(
    db: Session, reference_date: date | None = None
) -> dict[str, dict[str, Any]]:
    """
    Returns {canonical_name: {"30d": float|None, "90d": ..., "365d": ..., "unit": str, "last_data": date|None}}
    """
    today = reference_date or date.today()
    end_dt = _end_of_day(today)

    sleep_daily_365 = _build_sleep_daily_hours(
        db, _window_start_dt(today, 365), end_dt
    )

    out: dict[str, dict[str, Any]] = {}
    for canonical, (metric_type, agg, unit) in METRICS_TO_ROLL.items():
        last_row = (
            db.query(func.max(RawMeasurement.start_date))
            .filter(RawMeasurement.metric_type == metric_type)
            .scalar()
        )
        last_data = last_row.date() if last_row else None

        windows: dict[str, float | None] = {}
        for w in (30, 90, 365):
            ws = _window_start_dt(today, w)
            val: float | None = None
            if agg == "mean":
                val = _sql_mean(db, metric_type, ws, end_dt)
            elif agg == "daily_sum_then_mean":
                val = _daily_sum_then_mean(db, metric_type, ws, end_dt)
            elif agg == "sleep_duration_hours":
                val = _mean_sleep_for_window(sleep_daily_365, today, w)
            key = f"{w}d"
            windows[key] = val

        out[canonical] = {
            "30d": windows["30d"],
            "90d": windows["90d"],
            "365d": windows["365d"],
            "unit": unit,
            "last_data": last_data,
        }
    return out


def _fmt_val(v: float | None, canonical: str | None = None) -> str:
    if v is None:
        return "n/a"
    x = float(v)
    if canonical == "body_fat_pct":
        x *= 100.0
    ax = abs(x)
    if ax >= 1000:
        return f"{x:.0f}"
    if ax >= 100:
        return f"{x:.1f}"
    if ax >= 10:
        return f"{x:.2f}"
    return f"{x:.3g}"


def _trend_annotation(
    v30: float,
    v365: float | None,
    canonical: str,
    unit: str,
) -> str:
    if v365 is None:
        return "(stable)"
    # Low-variance sleep: absolute 2+ hours difference
    if canonical == "sleep_hours_daily" or "hrs" in unit:
        if abs(v30 - v365) > 2.0:
            return (
                "(trending up vs 365d baseline)"
                if v30 > v365
                else "(trending down vs 365d baseline)"
            )
        return "(stable)"
    # Percent / ratio style
    denom = abs(v365)
    if denom < 1e-9:
        if abs(v30 - v365) > 0.01:
            return (
                "(trending up vs 365d baseline)"
                if v30 > v365
                else "(trending down vs 365d baseline)"
            )
        return "(stable)"
    if abs(v30 - v365) / denom > 0.05:
        return (
            "(trending up vs 365d baseline)"
            if v30 > v365
            else "(trending down vs 365d baseline)"
        )
    return "(stable)"


def format_rollup_block(rollups: dict[str, dict[str, Any]]) -> str:
    lines: list[str] = []
    for canonical in METRICS_TO_ROLL.keys():
        block = rollups.get(canonical)
        if not block:
            continue
        v30 = block.get("30d")
        if v30 is None:
            continue
        v90 = block.get("90d")
        v365 = block.get("365d")
        unit = block.get("unit") or ""
        note = _trend_annotation(float(v30), float(v365) if v365 is not None else None, canonical, unit)
        line = (
            f"{canonical}: 30d={_fmt_val(v30, canonical)}, 90d={_fmt_val(v90, canonical)}, "
            f"365d={_fmt_val(v365, canonical)} {unit} {note}"
        )
        lines.append(line)
    return "\n".join(lines)
