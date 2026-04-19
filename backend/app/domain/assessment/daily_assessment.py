from app.db.repositories.lab_repository import get_trend_for_test

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

        metrics[test] = {
            "latest": latest,
            "previous": previous,
            "delta": (latest["value"] - previous["value"] if previous and latest["value"] is not None and previous["value"] is not None else None)
        }
    return metrics

def build_summary_text(snapshot):
    lines = []
    for test, data in snapshot.items():
        latest = data["latest"]
        delta = data["delta"]

        line = f"{test}: {latest['value']} {latest['unit']}"
        if delta is not None:
            if delta > 0: line += f" (↑ {abs(delta):.2f})"
            elif delta < 0: line += f" (↓ {abs(delta):.2f})"
            else: line += " (no change)"

        if latest["flag"]:
            line += f" [FLAG: {latest['flag']}]"

        lines.append(line)
    return "\n".join(lines)
