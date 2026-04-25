from app.db.repositories.lab_repository import get_trend_for_test
from app.db.models import LabTestCatalog
from app.domain.assessment.trend_analysis import compute_trend, format_trend_line


def build_health_snapshot(db):
    metrics = {}
    catalog_codes = [
        row.canonical_code
        for row in (
            db.query(LabTestCatalog)
            .filter(LabTestCatalog.active == 1)
            .order_by(LabTestCatalog.id)
            .all()
        )
    ]

    for code in catalog_codes:
        trend = get_trend_for_test(db, code)
        if not trend:
            continue

        latest = trend[-1]
        previous = trend[-2] if len(trend) > 1 else None

        series_for_trend = [{"date": row["date"], "value": row["value"]} for row in trend]
        trend_stats = compute_trend(series_for_trend)

        metrics[code] = {
            "latest": latest,
            "previous": previous,
            "delta": (
                latest["value"] - previous["value"]
                if previous
                and latest["value"] is not None
                and previous["value"] is not None
                else None
            ),
            "trend": trend_stats,
        }
    return metrics


def build_summary_text(snapshot):
    lines = []
    for test, data in snapshot.items():
        lines.append(format_trend_line(test, data, data.get("trend")))
    return "\n".join(lines)
