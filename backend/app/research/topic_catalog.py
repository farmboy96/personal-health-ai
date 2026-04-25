"""Pre-built PubMed research topics loaded from YAML seed data."""

from pathlib import Path

import yaml

_TOPICS_PATH = Path(__file__).resolve().parents[2] / "data" / "seed" / "topics.yaml"


def _load_topics() -> dict:
    payload = yaml.safe_load(_TOPICS_PATH.read_text(encoding="utf-8")) or {}
    return dict(payload.get("topics") or {})


TOPICS = _load_topics()
