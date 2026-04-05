from sqlalchemy.orm import Session
from app.db.models import LabResult


def get_trend_for_test(db: Session, test_code: str):
    rows = (
        db.query(LabResult)
        .filter(
            LabResult.canonical_test_code == test_code,
            LabResult.result_value_numeric.isnot(None)
        )
        .order_by(LabResult.lab_date.asc())
        .all()
    )

    return [
        {
            "date": r.lab_date,
            "value": r.result_value_numeric,
            "unit": r.unit,
            "flag": r.abnormal_flag
        }
        for r in rows
    ]