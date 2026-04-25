import os
import sys
from pathlib import Path
from typing import Any

import yaml

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import SessionLocal
from app.db.models import GeneticRecommendation


_SEED_PATH = Path(__file__).resolve().parents[1] / "data" / "seed" / "genetic_recommendations.yaml"


def _seed_rows() -> list[dict[str, Any]]:
    payload = yaml.safe_load(_SEED_PATH.read_text(encoding="utf-8")) or {}
    rows = payload.get("genetic_recommendations") or []
    return [dict(r) for r in rows]


def main():
    db = SessionLocal()
    try:
        rows = _seed_rows()
        added = 0
        updated = 0
        for r in rows:
            exists = (
                db.query(GeneticRecommendation)
                .filter(
                    GeneticRecommendation.rsid == r["rsid"],
                    GeneticRecommendation.category == r["category"],
                    GeneticRecommendation.recommendation_text == r["recommendation_text"],
                )
                .first()
            )
            if exists:
                changed = False
                for key, value in r.items():
                    if getattr(exists, key) != value:
                        setattr(exists, key, value)
                        changed = True
                if changed:
                    updated += 1
            else:
                db.add(GeneticRecommendation(**r))
                added += 1
        db.commit()
        total = db.query(GeneticRecommendation).count()
        print({"added": added, "updated": updated, "total": total})
    finally:
        db.close()


if __name__ == "__main__":
    main()
