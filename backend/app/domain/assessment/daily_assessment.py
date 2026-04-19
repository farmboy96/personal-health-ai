from app.db.repositories.lab_repository import get_trend_for_test
from app.domain.assessment.trend_analysis import compute_trend, format_trend_line


def build_health_snapshot(db):
    """
    Pull key metrics we care about.
    Keep this tight. No fluff.
    """
    metrics = {}
    key_tests = [
        "TSH",
        "A1C",
        "GLUCOSE",
        "VITAMIN_D_25_OH_TOTAL",
        "TESTOSTERONE_TOTAL",
        "TESTOSTERONE_FREE",
        "ESTRADIOL",
        "FERRITIN",
        "HS_CRP",
        "HOMOCYSTEINE",
        "TOTAL_CHOLESTEROL",
        "LDL",
        "HDL",
        "TRIGLYCERIDES",
        "INSULIN",
    ]

    for test in key_tests:
        trend = get_trend_for_test(db, test)
        if not trend: continue

        latest = trend[-1]
        previous = trend[-2] if len(trend) > 1 else None

        series_for_trend = [{"date": row["date"], "value": row["value"]} for row in trend]
        trend_stats = compute_trend(series_for_trend)

        metrics[test] = {
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
