"""
Streamlit dashboard for Personal Health AI (solo use, local only).

Run from repo root:
    backend\\.venv\\Scripts\\streamlit.exe run dashboard.py
"""

from __future__ import annotations

import sys
from datetime import date, datetime
from pathlib import Path

# --- Path: backend is the Python package root ---
_ROOT = Path(__file__).resolve().parent
_BACKEND = _ROOT / "backend"
if str(_BACKEND) not in sys.path:
    sys.path.insert(0, str(_BACKEND))

import streamlit as st
from sqlalchemy import desc, distinct, func

from app.application.generate_daily_summary import (
    execute_daily_summary,
    load_latest_summary,
)
from app.db.database import SessionLocal
from app.db.models import DailySummary, GeneticVariant, LabResult, RawMeasurement
from app.domain.assessment.apple_health_rollup import (
    METRICS_TO_ROLL,
    _build_sleep_daily_hours,
    _end_of_day,
    _trend_annotation,
    _window_start_dt,
    compute_rollups,
)
from app.domain.assessment.trend_analysis import compute_trend
from scipy.stats import linregress


# -----------------------------------------------------------------------------
# Helpers (queries & formatting)
# -----------------------------------------------------------------------------


def _session():
    return SessionLocal()


def _sql_date_cell_to_date(cell) -> date | None:
    if cell is None:
        return None
    if isinstance(cell, datetime):
        return cell.date()
    if isinstance(cell, date):
        return cell
    if isinstance(cell, str):
        return date.fromisoformat(cell[:10])
    return None


def fetch_recent_summaries(db, limit: int = 10) -> list[DailySummary]:
    return (
        db.query(DailySummary)
        .order_by(desc(DailySummary.created_at))
        .limit(limit)
        .all()
    )


def fetch_overview_row(db, explicit_id: int | None) -> DailySummary | None:
    if explicit_id is None:
        return load_latest_summary(db)
    return db.query(DailySummary).filter(DailySummary.id == explicit_id).first()


@st.cache_data(ttl=120)
def cached_distinct_canonical_codes() -> list[str]:
    db = _session()
    try:
        rows = (
            db.query(LabResult.canonical_test_code)
            .filter(LabResult.canonical_test_code.isnot(None))
            .distinct()
            .order_by(LabResult.canonical_test_code)
            .all()
        )
        return [r[0] for r in rows if r[0]]
    finally:
        db.close()


@st.cache_data(ttl=120)
def cached_lab_aggregate_stats() -> tuple[int, int, date | None]:
    db = _session()
    try:
        total = db.query(func.count(LabResult.id)).scalar() or 0
        distinct_tests = (
            db.query(func.count(distinct(LabResult.canonical_test_code)))
            .filter(LabResult.canonical_test_code.isnot(None))
            .scalar()
            or 0
        )
        latest = db.query(func.max(LabResult.lab_date)).scalar()
        return int(total), int(distinct_tests), latest
    finally:
        db.close()


def fetch_lab_series(db, canonical_code: str) -> list[LabResult]:
    return (
        db.query(LabResult)
        .filter(
            LabResult.canonical_test_code == canonical_code,
            LabResult.result_value_numeric.isnot(None),
        )
        .order_by(LabResult.lab_date.asc())
        .all()
    )


def fetch_physiology_sparkline_series(
    db, canonical: str
) -> tuple[list[date], list[float]]:
    """365-day daily series for sparklines (daily mean or daily sum or sleep hours)."""
    today = date.today()
    ws = _window_start_dt(today, 365)
    we = _end_of_day(today)
    metric_type, agg, _unit = METRICS_TO_ROLL[canonical]

    if agg == "sleep_duration_hours":
        daily = _build_sleep_daily_hours(db, ws, we)
        pts = sorted(daily.items())
        dates = [p[0] for p in pts]
        vals = [p[1] for p in pts]
        return dates, vals

    day_col = func.date(RawMeasurement.start_date)
    base_filter = (
        RawMeasurement.metric_type == metric_type,
        RawMeasurement.start_date >= ws,
        RawMeasurement.start_date <= we,
        RawMeasurement.value.isnot(None),
    )
    if agg == "mean":
        rows = (
            db.query(day_col, func.avg(RawMeasurement.value))
            .filter(*base_filter)
            .group_by(day_col)
            .order_by(day_col)
            .all()
        )
    else:
        rows = (
            db.query(day_col, func.sum(RawMeasurement.value))
            .filter(*base_filter)
            .group_by(day_col)
            .order_by(day_col)
            .all()
        )

    dates: list[date] = []
    vals: list[float] = []
    for day_cell, val in rows:
        d = _sql_date_cell_to_date(day_cell)
        if d is None or val is None:
            continue
        vx = float(val)
        if canonical == "body_fat_pct":
            vx *= 100.0
        dates.append(d)
        vals.append(vx)
    return dates, vals


def trend_arrow(v30: float | None, v365: float | None, canonical: str, unit: str) -> str:
    if v30 is None:
        return "—"
    ann = _trend_annotation(float(v30), float(v365) if v365 is not None else None, canonical, unit)
    if "up" in ann:
        return "↑"
    if "down" in ann:
        return "↓"
    return "→"


@st.cache_data(ttl=300)
def cached_genetic_variant_rows() -> list[dict]:
    db = _session()
    try:
        rows = (
            db.query(GeneticVariant)
            .order_by(desc(GeneticVariant.magnitude))
            .all()
        )
        out = []
        for r in rows:
            out.append(
                {
                    "rsid": r.rsid,
                    "genotype": r.genotype,
                    "magnitude": r.magnitude,
                    "repute": r.repute or "Not Set",
                    "genes": r.genes or "",
                    "summary": r.summary or "",
                }
            )
        return out
    finally:
        db.close()


def filter_genetics(
    rows: list[dict],
    min_mag: float,
    repute_sel: list[str],
    search: str,
) -> list[dict]:
    search_l = search.lower().strip()
    rep_filter_on = len(repute_sel) > 0
    rep_set = set(repute_sel)
    out: list[dict] = []
    for r in rows:
        mag = r["magnitude"]
        if mag is not None and mag < min_mag:
            continue
        if mag is None and min_mag > 0:
            continue
        rep = r["repute"]
        if rep_filter_on and rep not in rep_set:
            continue
        if search_l:
            blob = (r["summary"] + " " + r["genes"]).lower()
            if search_l not in blob:
                continue
        out.append(r)
    return out


def main() -> None:
    import pandas as pd
    import plotly.graph_objects as go

    st.set_page_config(
        page_title="Personal Health AI",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # --- Sidebar: summary history ---
    with st.sidebar:
        st.markdown("### Summary history")
        st.caption("Choose which saved daily summary drives the Overview tab.")
        db0 = _session()
        try:
            recent = fetch_recent_summaries(db0, 10)
        finally:
            db0.close()

        labels: list[str] = ["Latest (most recent run)"]
        ids: list[int | None] = [None]
        for s in recent:
            ts = s.created_at.strftime("%Y-%m-%d %H:%M:%S") if s.created_at else "?"
            labels.append(f"{ts} · #{s.id}")
            ids.append(s.id)

        choice = st.selectbox(
            "Active summary",
            labels,
            key="overview_summary_select",
        )
        picked_id = ids[labels.index(choice)]

        if st.button("Refresh Analysis", type="primary", use_container_width=True):
            with st.spinner("Regenerating summary (calls OpenAI)…"):
                execute_daily_summary()
            st.session_state["overview_summary_select"] = labels[0]
            st.success("Saved new daily summary.")
            st.rerun()

        st.divider()
        st.caption("Launch: `backend\\.venv\\Scripts\\streamlit.exe run dashboard.py`")

    # Resolve overview row
    db = _session()
    try:
        row = fetch_overview_row(db, picked_id)
        total_labs, distinct_codes, last_lab_date = cached_lab_aggregate_stats()
    finally:
        db.close()

    # --- Header ---
    today = date.today()
    st.title("Personal Health AI")
    st.subheader(today.strftime("%A, %B %d, %Y"))

    if row and row.created_at:
        st.caption(f"Last updated: **{row.created_at.strftime('%Y-%m-%d %H:%M:%S')}** · summary id **#{row.id}**")
    else:
        st.warning("No saved summary yet — use **Refresh Analysis** in the sidebar.")

    m1, m2, m3 = st.columns(3)
    m1.metric("Total lab rows", f"{total_labs:,}")
    m2.metric("Distinct canonical tests", f"{distinct_codes:,}")
    if last_lab_date:
        days_ago = (today - last_lab_date).days
        m3.metric("Days since last lab", days_ago)
    else:
        m3.metric("Days since last lab", "—")

    tab_ov, tab_lab, tab_phy, tab_gen = st.tabs(
        ["Overview", "Lab Trends", "Physiology", "Genetics"]
    )

    # ----- TAB 1 Overview -----
    with tab_ov:
        r1, r2 = st.columns([4, 1])
        with r2:
            if st.button("Refresh Analysis", key="ov_refresh"):
                with st.spinner("Regenerating summary…"):
                    execute_daily_summary()
                st.session_state["overview_summary_select"] = "Latest (most recent run)"
                st.rerun()
        if not row:
            st.info("Run **Refresh Analysis** to generate your first cached summary.")
        else:
            with st.expander("Lab Snapshot", expanded=True):
                st.code(row.summary_text or "", language=None)
            with st.expander("Physiology Rollups", expanded=True):
                st.code(row.physiology_rollups or "", language=None)
            with st.expander("AI Insights", expanded=True):
                st.markdown(row.ai_insights or "_No output_")

    # ----- TAB 2 Lab Trends -----
    with tab_lab:
        codes = cached_distinct_canonical_codes()
        if not codes:
            st.warning("No canonical lab codes in the database.")
        else:
            pick = st.selectbox("Canonical test code", codes, key="lab_code_pick")
            db = _session()
            try:
                series = fetch_lab_series(db, pick)
            finally:
                db.close()

            if not series:
                st.info("No numeric results for this code.")
            else:
                pts = [
                    {
                        "date": r.lab_date,
                        "value": float(r.result_value_numeric),
                    }
                    for r in series
                    if r.result_value_numeric is not None and r.lab_date is not None
                ]
                trend = compute_trend(
                    [{"date": p["date"], "value": p["value"]} for p in pts]
                )

                xs = [p["date"] for p in pts]
                ys = [p["value"] for p in pts]

                fig = go.Figure()
                fig.add_trace(
                    go.Scatter(
                        x=xs,
                        y=ys,
                        mode="lines+markers",
                        name="Labs",
                        hovertemplate="%{x|%Y-%m-%d}<br>value=%{y:.4g}<extra></extra>",
                    )
                )

                if trend is not None and len(pts) >= 3:
                    x_ord = [p["date"].toordinal() for p in pts]
                    lr = linregress(x_ord, ys)
                    x0, x1 = min(x_ord), max(x_ord)
                    y0 = lr.intercept + lr.slope * x0
                    y1 = lr.intercept + lr.slope * x1
                    d0 = date.fromordinal(int(x0))
                    d1 = date.fromordinal(int(x1))
                    fig.add_trace(
                        go.Scatter(
                            x=[d0, d1],
                            y=[y0, y1],
                            mode="lines",
                            name="Linear trend",
                            line=dict(dash="dash"),
                        )
                    )

                fig.update_layout(
                    margin=dict(l=10, r=10, t=40, b=10),
                    title=f"{pick} · n={len(pts)}",
                    xaxis_title="Lab date",
                    yaxis_title="Value",
                    hovermode="x unified",
                    height=420,
                )
                st.plotly_chart(fig, use_container_width=True)

                tbl = []
                for r in series:
                    tbl.append(
                        {
                            "lab_date": r.lab_date,
                            "value": r.result_value_numeric,
                            "unit": r.unit,
                            "flag": r.abnormal_flag,
                        }
                    )
                st.dataframe(pd.DataFrame(tbl), use_container_width=True, hide_index=True)

    # ----- TAB 3 Physiology -----
    with tab_phy:
        db = _session()
        try:
            roll = compute_rollups(db)
        finally:
            db.close()

        st.caption("Rolling windows vs today — sparklines show **last 365 days** (daily totals or daily means).")

        for canonical in METRICS_TO_ROLL.keys():
            info = roll.get(canonical)
            _mt, _agg, unit = METRICS_TO_ROLL[canonical]
            row_cols = st.columns([2, 1, 1, 1, 1, 4])

            v30 = info["30d"] if info else None
            v90 = info["90d"] if info else None
            v365 = info["365d"] if info else None

            def fmt(v: float | None) -> str:
                if v is None:
                    return "—"
                if canonical == "body_fat_pct":
                    v = v * 100.0
                return f"{v:.3g}"

            with row_cols[0]:
                st.markdown(f"**{canonical}**")
            with row_cols[1]:
                st.metric("30d", fmt(v30))
            with row_cols[2]:
                st.metric("90d", fmt(v90))
            with row_cols[3]:
                st.metric("365d", fmt(v365))
            with row_cols[4]:
                st.markdown(trend_arrow(v30, v365, canonical, unit))

            with row_cols[5]:
                db = _session()
                try:
                    dx, dy = fetch_physiology_sparkline_series(db, canonical)
                finally:
                    db.close()
                if dx and dy:
                    sf = go.Figure(
                        go.Scatter(
                            x=dx,
                            y=dy,
                            mode="lines",
                            line=dict(width=1.5),
                            hovertemplate="%{x|%Y-%m-%d}<br>%{y:.3g}<extra></extra>",
                        )
                    )
                    sf.update_layout(
                        height=120,
                        margin=dict(l=10, r=10, t=10, b=10),
                        showlegend=False,
                        xaxis=dict(visible=False),
                        yaxis=dict(visible=False),
                    )
                    st.plotly_chart(sf, use_container_width=True, config={"displayModeBar": False})
                else:
                    st.caption("_no series_")

            st.divider()

    # ----- TAB 4 Genetics -----
    with tab_gen:
        raw_rows = cached_genetic_variant_rows()
        c1, c2, c3 = st.columns([1, 1, 2])
        with c1:
            mag_min = st.slider("Minimum magnitude", 0.0, 6.0, 2.0, 0.1)
        with c2:
            rep_opts = ["Good", "Bad", "Mixed", "Not Set"]
            reps = st.multiselect("Repute", rep_opts, default=rep_opts)
        with c3:
            q = st.text_input("Search (summary + genes)", "")

        filtered = filter_genetics(raw_rows, mag_min, reps, q)
        df = pd.DataFrame(filtered)
        st.dataframe(df, use_container_width=True, hide_index=True)


if __name__ == "__main__":
    main()
