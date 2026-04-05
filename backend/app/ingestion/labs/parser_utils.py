import re
from typing import Optional

NUMERIC_REGEX = re.compile(r"[-+]?\d*\.?\d+")

def extract_numeric_value(value_text: str) -> Optional[float]:
    if not value_text:
        return None

    text = value_text.strip()

    # Fast reject (non-numeric common lab outputs)
    lowered = text.lower()
    if lowered in {"negative", "positive", "normal", "abnormal", "see note"}:
        return None

    # Reject obvious ranges (for now)
    if "-" in text and not text.strip().startswith("-"):
        return None

    # Extract first numeric match
    match = NUMERIC_REGEX.search(text)
    if not match:
        return None

    try:
        return float(match.group())
    except ValueError:
        return None