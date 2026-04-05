import sys
import os
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from app.db.database import SessionLocal
from app.db.models import LabResult
from scripts.debug_extract_lab_pdf import extract_pdf  # reuse logic
from app.domain.labs.normalization import (
    resolve_canonical_test,
    standardize_test_name,
)

import hashlib

def insert_rows(rows):
    db = SessionLocal()
    inserted = 0
    skipped = 0

    for row in rows:
        dedupe_hash = generate_dedupe_hash(row)

        exists = db.query(LabResult).filter_by(dedupe_hash=dedupe_hash).first()
        if exists:
            skipped += 1
            continue

        resolved = resolve_canonical_test(db, row["source_test_name"], source_scope="PDF")

        if not resolved:
            print(
                f"[UNMATCHED TEST NAME] raw='{row['source_test_name']}' "
                f"std='{standardize_test_name(row['source_test_name'])}'"
            )

        new_row = LabResult(
            lab_date=parse_date_safe(row["lab_date"]),
            source_test_name=row["source_test_name"],
            result_value_text=row["result_value_text"],
            unit=row["unit"],
            reference_range=row["reference_range"],
            abnormal_flag=row["abnormal_flag"],
            dedupe_hash=dedupe_hash,
            canonical_test_code=resolved["canonical_test_code"] if resolved else None,
            canonical_test_name=resolved["canonical_test_name"] if resolved else None,
            test_category=resolved["test_category"] if resolved else None,
            panel_name=resolved["panel_name"] if resolved else None,
        )

        db.add(new_row)
        inserted += 1

    db.commit()
    db.close()

    print(f"\nInserted: {inserted}")
    print(f"Skipped (duplicates): {skipped}")

def parse_date_safe(date_str):
    try:
        return datetime.strptime(date_str, "%m/%d/%y").date()
    except:
        return None

def generate_dedupe_hash(row: dict) -> str:
    key = f"{row['lab_date']}|{row['source_test_name']}|{row['result_value_text']}|{row['unit']}"
    return hashlib.sha256(key.encode()).hexdigest()


def insert_rows(rows):
    db = SessionLocal()
    inserted = 0
    skipped = 0

    for row in rows:
        dedupe_hash = generate_dedupe_hash(row)

        exists = db.query(LabResult).filter_by(dedupe_hash=dedupe_hash).first()
        if exists:
            skipped += 1
            continue

        new_row = LabResult(
            lab_date=parse_date_safe(row["lab_date"]),
            source_test_name=row["source_test_name"],
            result_value_text=row["result_value_text"],
            unit=row["unit"],
            reference_range=row["reference_range"],
            abnormal_flag=row["abnormal_flag"],
            dedupe_hash=dedupe_hash,
        )

        db.add(new_row)
        inserted += 1

    db.commit()
    db.close()

    print(f"\nInserted: {inserted}")
    print(f"Skipped (duplicates): {skipped}")


def main():
    pdf_path = Path(sys.argv[1]).resolve()

    # reuse debug extractor but capture output instead of printing
    rows = extract_pdf(pdf_path)  # we will tweak this next if needed

    insert_rows(rows)


if __name__ == "__main__":
    main()