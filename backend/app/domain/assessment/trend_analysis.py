"""
Multi-point statistical trends for lab biomarkers (linear regression over time).
"""

from __future__ import annotations

from datetime import date, datetime
from typing import Any

from scipy.stats import linregress


def _normalize_date(d: Any) -> date | None:
    if d is None:
        return None
    if isinstance(d, datetime):
        return d.date()
    if isinstance(d, date):
        return d
    return None


def compute_trend(data_points: list[dict[str, Any]]) -> dict[str, Any] | None:
    """
    Compute linear trend over dated numeric points.
    Returns None if fewer than 3 usable points.
    """
    pts: list[tuple[date, float]] = []
    for p in data_points:
        v = p.get("value")
        d = _normalize_date(p.get("date"))
        if v is None or d is None:
            continue
        try:
            pts.append((d, float(v)))
        except (TypeError, ValueError):
            continue

    pts.sort(key=lambda x: x[0])
    n = len(pts)
    if n < 3:
        return None

    first_date, first_value = pts[0]
    latest_date, latest_value = pts[-1]

    total_change = latest_value - first_value
    if first_value != 0:
        total_change_pct = (total_change / first_value) * 100.0
    else:
        total_change_pct = float("nan")

    x_ord = [p[0].toordinal() for p in pts]
    y_vals = [p[1] for p in pts]

    lr = linregress(x_ord, y_vals)
    slope_per_day = lr.slope
    slope_per_year = slope_per_day * 365.25
    r_squared = float(lr.rvalue**2)

    mean_val = sum(y_vals) / n
    pct_threshold = 0.05 * abs(mean_val)
    if pct_threshold == 0:
        pct_threshold = max(abs(latest_value), abs(first_value), 1e-12) * 0.05

    if abs(slope_per_year) <= pct_threshold:
        trend_direction = "stable"
    elif slope_per_year > 0:
        trend_direction = "rising"
    else:
        trend_direction = "falling"

    return {
        "n": n,
        "first_value": first_value,
        "latest_value": latest_value,
        "first_date": first_date,
        "latest_date": latest_date,
        "total_change": total_change,
        "total_change_pct": total_change_pct,
        "slope_per_year": slope_per_year,
        "r_squared": r_squared,
        "trend_direction": trend_direction,
    }


def _format_base_line(canonical_code: str, entry: dict[str, Any]) -> str:
    latest = entry["latest"]
    delta = entry.get("delta")

    val = latest.get("value")
    unit = latest.get("unit") or ""
    line = f"{canonical_code}: {val} {unit}".strip()
    if delta is not None:
        if delta > 0:
            line += f" (↑ {abs(delta):.2f})"
        elif delta < 0:
            line += f" (↓ {abs(delta):.2f})"
        else:
            line += " (no change)"

    flag = latest.get("flag")
    if flag:
        line += f" [FLAG: {flag}]"

    return line


def _fmt_num(x: float) -> str:
    if x != x:  # NaN
        return "—"
    ax = abs(x)
    if ax >= 100:
        return f"{x:.1f}"
    if ax >= 10:
        return f"{x:.2f}"
    return f"{x:.3g}"


def format_trend_line(
    canonical_code: str,
    latest_snapshot_entry: dict[str, Any],
    trend_dict: dict[str, Any] | None,
) -> str:
    base = _format_base_line(canonical_code, latest_snapshot_entry)
    if trend_dict is None:
        return base

    fd = trend_dict["first_date"]
    ld = trend_dict["latest_date"]
    if isinstance(fd, datetime):
        fd = fd.date()
    if isinstance(ld, datetime):
        ld = ld.date()
    span_days = (ld - fd).days
    years = span_days / 365.25 if span_days >= 0 else 0.0

    fv = trend_dict["first_value"]
    lv = trend_dict["latest_value"]
    slope = trend_dict["slope_per_year"]
    r2 = trend_dict["r_squared"]
    direction = trend_dict["trend_direction"]

    trend_bit = (
        f" | trend: {_fmt_num(fv)} → {_fmt_num(lv)} over {years:.1f} yrs "
        f"({_fmt_num(slope)}/yr, {direction}, R²={r2:.2f})"
    )
    return base + trend_bit
