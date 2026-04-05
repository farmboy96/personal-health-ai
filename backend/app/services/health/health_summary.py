"""
DEPRECATED: 
This file is slated for deletion.
- Domain logic has migrated natively to `app.domain.assessment.daily_assessment`.
- OpenAI prompts have migrated to `app.ai.health_interpreter`.
"""
from app.db.repositories.lab_repository import get_trend_for_test


def build_health_snapshot(db):
    """
    Pull key metrics we care about.
    Keep this tight. No fluff.
    """

    metrics = {}

    key_tests = [
        "TSH",
        "HEMOGLOBIN_A1C",
        "VITAMIN_D",
        "TESTOSTERONE_TOTAL",
        "ESTRADIOL",
        "FERRITIN",
        "HS_CRP",
        "HOMOCYSTEINE",
    ]

    for test in key_tests:
        trend = get_trend_for_test(db, test)

        if not trend:
            continue

        latest = trend[-1]
        previous = trend[-2] if len(trend) > 1 else None

        metrics[test] = {
            "latest": latest,
            "previous": previous,
            "delta": (
                latest["value"] - previous["value"]
                if previous else None
            )
        }

    return metrics

def build_summary_text(snapshot):
    lines = []

    for test, data in snapshot.items():
        latest = data["latest"]
        delta = data["delta"]

        line = f"{test}: {latest['value']} {latest['unit']}"

        if delta is not None:
            direction = "↑" if delta > 0 else "↓"
            line += f" ({direction} {abs(delta):.2f})"

        if latest["flag"]:
            line += f" [FLAG: {latest['flag']}]"

        lines.append(line)

    return "\n".join(lines)

from app.db.repositories.lab_repository import get_trend_for_test
import os
from openai import OpenAI

client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))


def build_health_snapshot(db):
    metrics = {}

    key_tests = [
        "TSH",
        "HEMOGLOBIN_A1C",
        "VITAMIN_D",
        "TESTOSTERONE_TOTAL",
        "ESTRADIOL",
        "FERRITIN",
        "HS_CRP",
        "HOMOCYSTEINE",
    ]

    for test in key_tests:
        trend = get_trend_for_test(db, test)

        if not trend:
            continue

        latest = trend[-1]
        previous = trend[-2] if len(trend) > 1 else None

        metrics[test] = {
            "latest": latest,
            "previous": previous,
            "delta": (
                latest["value"] - previous["value"]
                if previous and latest["value"] is not None and previous["value"] is not None
                else None
            )
        }

    return metrics


def build_summary_text(snapshot):
    lines = []

    for test, data in snapshot.items():
        latest = data["latest"]
        delta = data["delta"]

        line = f"{test}: {latest['value']} {latest['unit']}"

        if delta is not None:
            if delta > 0:
                line += f" (↑ {abs(delta):.2f})"
            elif delta < 0:
                line += f" (↓ {abs(delta):.2f})"
            else:
                line += " (no change)"

        if latest["flag"]:
            line += f" [FLAG: {latest['flag']}]"

        lines.append(line)

    return "\n".join(lines)


def generate_ai_insights(summary_text: str) -> str:
    prompt = f"""
You are a blunt, practical health analyst.

Analyze the following lab trends and provide:

1. What stands out
2. Likely causes or pattern connections
3. What to watch
4. Practical actions

Be concise. No fluff. No disclaimers.

Data:
{summary_text}
"""

    response = client.chat.completions.create(
        model="gpt-5",
        messages=[
            {
                "role": "system",
                "content": "You analyze health data and give concise, practical insights."
            },
            {
                "role": "user",
                "content": prompt
            }
        ],
    )

    return response.choices[0].message.content.strip()


def generate_health_summary(db):
    snapshot = build_health_snapshot(db)
    summary = build_summary_text(snapshot)
    ai_output = generate_ai_insights(summary)
    return summary, ai_output