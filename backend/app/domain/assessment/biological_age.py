"""
Biological age estimators: Levine Phenotypic Age, NTNU-style fitness age (VO2max-based),
and Framingham general CVD 10-year risk heart age (D'Agostino et al. 2008).

References:
- Levine ME (2018) PMID 30496326 / DOI 10.18632/aging.101414
- Nes BM et al. (2013) VO2max and fitness age (NTNU World Fitness Level) — fitness-age
  interpolation here is a documented simplification; primary citation for VO2 estimation.
- D'Agostino RB et al. (2008) Circulation — Framingham general CVD risk (lipids model).
"""

from __future__ import annotations

import math
import re
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.db.models import LabResult, RawMeasurement

OBI_APP_SOURCE = "obi_app"
BP_SYSTOLIC_METRIC = "BP_SYSTOLIC"
BP_DIASTOLIC_METRIC = "BP_DIASTOLIC"
OBI_PULSE_METRIC = "OBI_PULSE"

PHENOTYPIC_CODES = (
    "ALBUMIN",
    "CREATININE",
    "GLUCOSE",
    "HS_CRP",
    "LYMPHOCYTES",
    "MCV",
    "RDW",
    "ALKALINE_PHOSPHATASE",
    # Canonical in lab_test_catalog (alias "WBC")
    "WHITE_BLOOD_CELL_COUNT",
)

FRAMINGHAM_LIPID_CODES = ("TOTAL_CHOLESTEROL", "HDL")

RHR_METRIC = "HKQuantityTypeIdentifierRestingHeartRate"


def _empty_payload(
    *,
    chronological_age: float,
    computed_for_date: date | None,
    computable: bool,
    missing_inputs: list[str],
    value: float | None = None,
    delta: float | None = None,
    components: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "value": float(value) if value is not None else float("nan"),
        "chronological_age": float(chronological_age),
        "delta": float(delta) if delta is not None else float("nan"),
        "components": components or {},
        "computed_for_date": computed_for_date,
        "computable": computable,
        "missing_inputs": missing_inputs,
    }


def _parse_chronological_age_from_context() -> float:
    from app.core.user_context import USER_CONTEXT

    m = re.search(r"Age:\s*(\d+)", USER_CONTEXT)
    if m:
        return float(m.group(1))
    return 54.0


def _parse_height_weight_bmi() -> tuple[float | None, float | None, float | None]:
    """Returns (height_in, weight_lb, bmi) from USER_CONTEXT; BMI computed if both present."""
    from app.core.user_context import USER_CONTEXT

    hm = re.search(r"Height/weight:\s*(\d+)['\"]\s*(\d+)\"(?:,\s*|\s+)(\d+)\s*lbs?", USER_CONTEXT, re.I)
    if hm:
        ft = int(hm.group(1))
        inch = int(hm.group(2))
        lb = float(hm.group(3))
        h_in = ft * 12 + inch
        if h_in > 0:
            bmi = (lb / (h_in * h_in)) * 703.0
            return float(h_in), lb, bmi
    return None, None, None


def _candidate_draw_dates(db: Session, as_of_date: date, window_days: int) -> list[date]:
    lo = as_of_date - timedelta(days=window_days)
    hi = as_of_date + timedelta(days=window_days)
    rows = (
        db.query(LabResult.lab_date)
        .filter(LabResult.lab_date >= lo, LabResult.lab_date <= hi)
        .distinct()
        .all()
    )
    dates = sorted({r[0] for r in rows if r[0]}, key=lambda d: abs((d - as_of_date).days))
    return dates


def _lab_value_on_date(db: Session, canonical_code: str, draw_date: date) -> float | None:
    row = (
        db.query(LabResult)
        .filter(
            LabResult.canonical_test_code == canonical_code,
            LabResult.lab_date == draw_date,
            LabResult.result_value_numeric.isnot(None),
        )
        .first()
    )
    if not row:
        return None
    return float(row.result_value_numeric)


def _resolve_phenotypic_draw(
    db: Session, as_of_date: date, window_days: int = 60
) -> tuple[date | None, dict[str, float], list[str]]:
    for draw in _candidate_draw_dates(db, as_of_date, window_days):
        vals: dict[str, float] = {}
        ok = True
        for code in PHENOTYPIC_CODES:
            v = _lab_value_on_date(db, code, draw)
            if v is None:
                ok = False
                break
            vals[code] = v
        if ok:
            return draw, vals, []
    dates = _candidate_draw_dates(db, as_of_date, window_days)
    if not dates:
        return None, {}, list(PHENOTYPIC_CODES)
    draw = dates[0]
    missing: list[str] = []
    for code in PHENOTYPIC_CODES:
        if _lab_value_on_date(db, code, draw) is None:
            missing.append(code)
    return None, {}, sorted(set(missing))


def _resolve_lipid_draw(
    db: Session, as_of_date: date, window_days: int = 60
) -> tuple[date | None, float | None, float | None, list[str]]:
    missing: list[str] = []
    for draw in _candidate_draw_dates(db, as_of_date, window_days):
        tc = _lab_value_on_date(db, "TOTAL_CHOLESTEROL", draw)
        hdl = _lab_value_on_date(db, "HDL", draw)
        if tc is not None and hdl is not None:
            return draw, tc, hdl, []
    for code in FRAMINGHAM_LIPID_CODES:
        v = None
        for draw in _candidate_draw_dates(db, as_of_date, window_days):
            x = _lab_value_on_date(db, code, draw)
            if x is not None:
                v = x
                break
        if v is None:
            missing.append(code)
    return None, None, None, missing


def _build_phenotypic_result(
    raw: dict[str, float], chrono: float, draw: date
) -> dict[str, Any] | None:
    albumin_g_L = raw["ALBUMIN"] * 10.0
    creat_umol_L = raw["CREATININE"] * 88.4
    glucose_mmol_L = raw["GLUCOSE"] / 18.0
    crp = max(float(raw["HS_CRP"]), 1e-6)
    ln_crp = math.log(crp)
    lymph_pct = raw["LYMPHOCYTES"]
    mcv = raw["MCV"]
    rdw = raw["RDW"]
    alp = raw["ALKALINE_PHOSPHATASE"]
    wbc = raw["WHITE_BLOOD_CELL_COUNT"]

    xb = (
        -19.907
        - 0.0336 * albumin_g_L
        + 0.0095 * creat_umol_L
        + 0.1953 * glucose_mmol_L
        + 0.0954 * ln_crp
        - 0.0120 * lymph_pct
        + 0.0268 * mcv
        + 0.3306 * rdw
        + 0.00188 * alp
        + 0.0554 * wbc
        + 0.0804 * chrono
    )

    inner = -1.51714 * math.exp(xb) / 0.0076927
    try:
        M = 1.0 - math.exp(inner)
        if M <= 0 or M >= 1:
            raise ValueError("M out of range")
        pheno = 141.50225 + math.log(-0.00553 * math.log(1.0 - M)) / 0.09165
    except (ValueError, OverflowError, ZeroDivisionError):
        return None

    delta = pheno - chrono
    components = {
        "draw_date": draw.isoformat(),
        "albumin_g_per_L": albumin_g_L,
        "creatinine_umol_per_L": creat_umol_L,
        "glucose_mmol_per_L": glucose_mmol_L,
        "crp_mg_per_L": crp,
        "ln_crp": ln_crp,
        "lymphocyte_percent": lymph_pct,
        "mcv_fL": mcv,
        "rdw_percent": rdw,
        "alkaline_phosphatase_U_per_L": alp,
        "wbc_1000_per_uL": wbc,
        "xb_linear_term": xb,
        "M": M,
        "phenotypic_age": pheno,
    }
    return {
        "value": float(pheno),
        "chronological_age": float(chrono),
        "delta": float(delta),
        "components": components,
        "computed_for_date": draw,
        "computable": True,
        "missing_inputs": [],
    }


def compute_phenotypic_age(db: Session, as_of_date: date) -> dict[str, Any]:
    """
    Levine Phenotypic Age (2018). Biomarkers from one CBC/chemistry draw within ±60 days.
    """
    chrono = _parse_chronological_age_from_context()
    draw, raw, missing = _resolve_phenotypic_draw(db, as_of_date)
    if draw is None:
        return _empty_payload(
            chronological_age=chrono,
            computed_for_date=None,
            computable=False,
            missing_inputs=missing or list(PHENOTYPIC_CODES),
        )

    built = _build_phenotypic_result(raw, chrono, draw)
    if built is None:
        xb_stub = {"raw_keys": list(raw.keys())}
        return _empty_payload(
            chronological_age=chrono,
            computed_for_date=draw,
            computable=False,
            missing_inputs=["numerical_failure"],
            components=xb_stub,
        )
    return built


def _apple_health_rhr_30d_average_bpm(db: Session, as_of_date: date) -> float | None:
    """Mean HKQuantityTypeIdentifierRestingHeartRate over [as_of_date-30d, as_of_date] (preferred for fitness age)."""
    start = datetime.combine(as_of_date - timedelta(days=30), datetime.min.time())
    end = datetime.combine(as_of_date, datetime.max.time())
    q = (
        db.query(func.avg(RawMeasurement.value))
        .filter(
            RawMeasurement.metric_type == RHR_METRIC,
            RawMeasurement.start_date >= start,
            RawMeasurement.start_date <= end,
            RawMeasurement.value.isnot(None),
        )
        .scalar()
    )
    if q is None:
        return None
    return float(q)


def _obi_seated_pulse_nearest_bpm(db: Session, as_of_date: date) -> tuple[float | None, date | None]:
    """OBI donation seated pulse (not true RHR) — nearest absolute date to as_of_date."""
    rows = (
        db.query(RawMeasurement)
        .filter(
            RawMeasurement.metric_type == OBI_PULSE_METRIC,
            RawMeasurement.source_name == OBI_APP_SOURCE,
            RawMeasurement.value.isnot(None),
        )
        .all()
    )
    if not rows:
        return None, None
    best = min(rows, key=lambda r: abs((r.start_date.date() - as_of_date).days))
    return (float(best.value), best.start_date.date()) if best.value is not None else (None, None)


def compute_fitness_age(db: Session, as_of_date: date) -> dict[str, Any]:
    """
    NTNU-style fitness age via non-exercise VO2max estimate + linear age adjustment.

    VO2max equation (men): documented approximation combining published predictors;
    fitness_age linear mapping vs population average VO2 ~35 mL/kg/min at mid-50s is a
    simplification — see Nes et al. 2013 for the World Fitness Level line of work.

    Physical activity score for Robert = 5 (vigorous >=30 min, >=3x/week per user context).

    Resting HR hierarchy:
    1) Apple Health 30-day average RestingHeartRate ending on as_of_date (true RHR).
    2) Fallback: nearest OBI seated pulse at donation (less precise).
    """
    chrono = _parse_chronological_age_from_context()
    missing: list[str] = []

    rhr_source = ""
    rhr_detail = ""
    ah_avg = _apple_health_rhr_30d_average_bpm(db, as_of_date)
    if ah_avg is not None:
        rhr_used = ah_avg
        rhr_source = "apple_health_30d_avg"
        rhr_detail = "30-day mean of HKQuantityTypeIdentifierRestingHeartRate through as_of_date"
    else:
        obi_pulse, obi_d = _obi_seated_pulse_nearest_bpm(db, as_of_date)
        if obi_pulse is not None:
            rhr_used = obi_pulse
            rhr_source = "obi_seated_pulse_fallback"
            rhr_detail = (
                f"Seated pulse at OBI donation on {obi_d.isoformat() if obi_d else '?'} "
                "(not true resting heart rate — lower precision than Apple Health RHR)"
            )
        else:
            rhr_used = None

    _, _, bmi_static = _parse_height_weight_bmi()
    bmi_roll = _bmi_from_rollups(db)
    bmi = bmi_roll if bmi_roll is not None else bmi_static
    if bmi is None:
        missing.append("bmi_height_weight")

    if rhr_used is None:
        missing.append("resting_hr_apple_30d_avg_or_obi_pulse_fallback")

    if missing:
        return _empty_payload(
            chronological_age=chrono,
            computed_for_date=as_of_date,
            computable=False,
            missing_inputs=missing,
        )

    activity_score = 5.0  # vigorous exercise per patient profile (BJJ + conditioning)

    vo2max = (
        21.2870
        + (0.1654 * chrono)
        - (0.1612 * bmi)
        - (0.1845 * rhr_used)
        + 6.2
        + activity_score
    )

    # Approximate age-adjusted population mean VO2 for men ~54yo (ml/kg/min); documented shortcut.
    age_adjusted_avg_vo2max = 35.0
    fitness_age = chrono - (20.0 * (vo2max - age_adjusted_avg_vo2max) / age_adjusted_avg_vo2max)
    delta = fitness_age - chrono

    components = {
        "resting_hr_bpm_used": rhr_used,
        "rhr_source": rhr_source,
        "rhr_detail": rhr_detail,
        "bmi": bmi,
        "bmi_source": "apple_health_body_mass" if bmi_roll is not None else "user_context_height_weight",
        "activity_score_0_to_5": activity_score,
        "vo2max_estimate_ml_kg_min": vo2max,
        "age_adjusted_avg_vo2max_reference": age_adjusted_avg_vo2max,
        "note": "Fitness age mapping is an approximation; see Nes et al. 2013 / NTNU fitness-age concept.",
    }
    return {
        "value": float(fitness_age),
        "chronological_age": float(chrono),
        "delta": float(delta),
        "components": components,
        "computed_for_date": as_of_date,
        "computable": True,
        "missing_inputs": [],
    }


def _bmi_from_rollups(db: Session) -> float | None:
    """Derive BMI from latest Apple Health body mass (lb) and static height when possible."""
    h_in, _, _ = _parse_height_weight_bmi()
    if h_in is None:
        return None
    row = (
        db.query(RawMeasurement)
        .filter(
            RawMeasurement.metric_type == "HKQuantityTypeIdentifierBodyMass",
            RawMeasurement.value.isnot(None),
        )
        .order_by(RawMeasurement.start_date.desc())
        .first()
    )
    if not row or row.value is None:
        return None
    lb = float(row.value)
    return (lb / (h_in * h_in)) * 703.0


def framingham_10yr_cvd_risk_men(
    *,
    age: float,
    total_chol_mg_dl: float,
    hdl_mg_dl: float,
    sbp_mmhg: float,
    hypertension_treatment: bool,
    smoker: bool,
    diabetes: bool,
) -> float:
    """General CVD 10-year risk — men, laboratory-based model (D'Agostino 2008 table)."""
    ln_age = math.log(age)
    ln_tc = math.log(total_chol_mg_dl)
    ln_hdl = math.log(hdl_mg_dl)
    ln_sbp = math.log(sbp_mmhg)
    sbp_term = (1.99881 if hypertension_treatment else 1.93303) * ln_sbp
    sum_beta = (
        3.06117 * ln_age
        + 1.12370 * ln_tc
        - 0.93263 * ln_hdl
        + sbp_term
        + 0.65451 * (1.0 if smoker else 0.0)
        + 0.57367 * (1.0 if diabetes else 0.0)
    )
    risk = 1.0 - math.pow(0.88936, math.exp(sum_beta - 23.9802))
    return float(min(max(risk, 0.0), 1.0))


def _heart_age_men_lipids(
    risk_target: float,
    *,
    sbp_mmhg: float,
    hypertension_treatment: bool,
    smoker: bool,
    diabetes: bool,
    tc_ref: float = 180.0,
    hdl_ref: float = 45.0,
) -> float:
    """
    Age A such that a reference man with 'optimal' lipids (TC/HDL), same BP/smoking/diabetes status,
    has the same 10-year Framingham general CVD risk (lipid model).
    """
    lo, hi = 30.0, 95.0
    for _ in range(60):
        mid = (lo + hi) / 2.0
        r = framingham_10yr_cvd_risk_men(
            age=mid,
            total_chol_mg_dl=tc_ref,
            hdl_mg_dl=hdl_ref,
            sbp_mmhg=sbp_mmhg,
            hypertension_treatment=hypertension_treatment,
            smoker=smoker,
            diabetes=diabetes,
        )
        if r < risk_target:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2.0


def compute_framingham_heart_age(db: Session, as_of_date: date) -> dict[str, Any]:
    """
    Framingham 'heart age' — age of a reference man (ideal TC 180, HDL 45, same BP/smoking/dx flags)
    with the same 10-year general CVD risk as the patient (lipid model).

    SBP from OBI screening BP when available (see _resolve_bp_for_framingham); else Apple Health cuff;
    else default 120 mmHg untreated assumption.
    """
    chrono = _parse_chronological_age_from_context()
    draw, tc, hdl, missing = _resolve_lipid_draw(db, as_of_date)
    if tc is None or hdl is None:
        return _empty_payload(
            chronological_age=chrono,
            computed_for_date=None,
            computable=False,
            missing_inputs=missing or ["TOTAL_CHOLESTEROL", "HDL"],
        )

    sbp, sbp_assumption, dbp_used = _resolve_bp_for_framingham(db, as_of_date)

    risk_patient = framingham_10yr_cvd_risk_men(
        age=chrono,
        total_chol_mg_dl=tc,
        hdl_mg_dl=hdl,
        sbp_mmhg=sbp,
        hypertension_treatment=False,
        smoker=False,
        diabetes=False,
    )

    heart_age = _heart_age_men_lipids(
        risk_patient,
        sbp_mmhg=sbp,
        hypertension_treatment=False,
        smoker=False,
        diabetes=False,
    )

    delta = heart_age - chrono
    components = {
        "lab_draw_date": draw.isoformat() if draw else None,
        "total_cholesterol_mg_dl": tc,
        "hdl_mg_dl": hdl,
        "systolic_bp_mmhg": sbp,
        "sbp_assumption": sbp_assumption,
        "hypertension_treatment": False,
        "smoking": False,
        "diabetes": False,
        "ten_year_cvd_risk": risk_patient,
        "reference_lipids_tc_hdl": {"tc_mg_dl": 180.0, "hdl_mg_dl": 45.0},
        "heart_age_years": heart_age,
        "diastolic_bp_mmhg_used": dbp_used,
    }
    return {
        "value": float(heart_age),
        "chronological_age": float(chrono),
        "delta": float(delta),
        "components": components,
        "computed_for_date": draw if draw else as_of_date,
        "computable": True,
        "missing_inputs": [],
    }


def _obi_bp_pair_for_date(db: Session, day: date) -> tuple[float | None, float | None]:
    start = datetime.combine(day, datetime.min.time())
    end = datetime.combine(day, datetime.max.time())
    sys_row = (
        db.query(RawMeasurement)
        .filter(
            RawMeasurement.metric_type == BP_SYSTOLIC_METRIC,
            RawMeasurement.source_name == OBI_APP_SOURCE,
            RawMeasurement.start_date >= start,
            RawMeasurement.start_date <= end,
            RawMeasurement.value.isnot(None),
        )
        .first()
    )
    dia_row = (
        db.query(RawMeasurement)
        .filter(
            RawMeasurement.metric_type == BP_DIASTOLIC_METRIC,
            RawMeasurement.source_name == OBI_APP_SOURCE,
            RawMeasurement.start_date >= start,
            RawMeasurement.start_date <= end,
            RawMeasurement.value.isnot(None),
        )
        .first()
    )
    sbp = float(sys_row.value) if sys_row and sys_row.value is not None else None
    dbp = float(dia_row.value) if dia_row and dia_row.value is not None else None
    return sbp, dbp


def _resolve_bp_for_framingham(db: Session, as_of_date: date) -> tuple[float, str, float | None]:
    """
    Systolic BP for Framingham:
    1) OBI finger-stick/cuff screening: most recent BP_SYSTOLIC on or before as_of_date (paired with
       BP_DIASTOLIC from the same calendar day when present).
    2) If no prior OBI reading, use OBI reading with nearest absolute date to as_of_date.
    3) Else Apple Health systolic in a window around as_of_date (legacy fallback).
    4) Else default 120 mmHg (untreated assumption; document).

    Method (1) matches clinical “last known BP before index date” for risk scoring.
    """
    rows = (
        db.query(RawMeasurement)
        .filter(
            RawMeasurement.metric_type == BP_SYSTOLIC_METRIC,
            RawMeasurement.source_name == OBI_APP_SOURCE,
            RawMeasurement.value.isnot(None),
        )
        .all()
    )
    if rows:
        on_or_before = [r for r in rows if r.start_date.date() <= as_of_date]
        if on_or_before:
            pick = max(on_or_before, key=lambda r: r.start_date)
            note = "obi_systolic_most_recent_on_or_before_lab_date"
        else:
            pick = min(rows, key=lambda r: abs((r.start_date.date() - as_of_date).days))
            note = "obi_systolic_nearest_absolute_no_prior_reading"
        d = pick.start_date.date()
        sbp = float(pick.value)
        _, dbp = _obi_bp_pair_for_date(db, d)
        detail = f"{note}:{d.isoformat()}"
        return sbp, detail, dbp

    # Apple Health fallback (watch / phone cuff)
    candidates = (
        "HKQuantityTypeIdentifierBloodPressureSystolic",
        "HKQuantityTypeIdentifierBloodPressure",
    )
    window_days = 180
    center = datetime.combine(as_of_date, datetime.min.time())
    lo = center - timedelta(days=window_days)
    hi = center + timedelta(days=window_days)

    for mt in candidates:
        ah_rows = (
            db.query(RawMeasurement)
            .filter(
                RawMeasurement.metric_type == mt,
                RawMeasurement.start_date >= lo,
                RawMeasurement.start_date <= hi,
                RawMeasurement.value.isnot(None),
            )
            .all()
        )
        if not ah_rows:
            continue
        best = min(ah_rows, key=lambda r: abs((r.start_date.date() - as_of_date).days))
        if best.value is None:
            continue
        v = float(best.value)
        if mt.endswith("BloodPressure") and v > 300:
            continue
        return v, f"apple_health:{mt}", None

    return 120.0, "default_120_not_on_hypertension_meds", None


def phenotypic_age_history(db: Session, max_points: int = 40) -> list[dict[str, Any]]:
    """Lab dates (chronological) where a full phenotypic-age panel exists on that date."""
    chrono = _parse_chronological_age_from_context()
    dates_rows = (
        db.query(LabResult.lab_date)
        .filter(LabResult.lab_date.isnot(None))
        .distinct()
        .order_by(LabResult.lab_date.asc())
        .all()
    )
    out: list[dict[str, Any]] = []
    for (d,) in dates_rows:
        if d is None:
            continue
        raw: dict[str, float] = {}
        skip = False
        for code in PHENOTYPIC_CODES:
            v = _lab_value_on_date(db, code, d)
            if v is None:
                skip = True
                break
            raw[code] = v
        if skip:
            continue
        built = _build_phenotypic_result(raw, chrono, d)
        if not built:
            continue
        out.append(
            {
                "lab_date": d.isoformat(),
                "phenotypic_age": built["value"],
                "delta": built["delta"],
            }
        )
        if len(out) >= max_points:
            break
    return out
