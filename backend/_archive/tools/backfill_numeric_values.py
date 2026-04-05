import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app.db.database import SessionLocal
from app.db.models import LabResult
from app.services.labs.value_parser import extract_numeric_value


def main():
    db = SessionLocal()

    rows = db.query(LabResult).all()

    updated = 0
    skipped = 0

    for row in rows:
        if row.result_value_numeric is not None:
            skipped += 1
            continue

        numeric = extract_numeric_value(row.result_value_text)

        if numeric is not None:
            row.result_value_numeric = numeric
            updated += 1

    db.commit()

    print(f"Updated: {updated}")
    print(f"Skipped (already had value): {skipped}")


if __name__ == "__main__":
    main()