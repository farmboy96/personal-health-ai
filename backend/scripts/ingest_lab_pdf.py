import sys
import os
from pathlib import Path

sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from app.db.database import SessionLocal
from app.db.models import LabResult
from app.ingestion.labs.pdf_ingest import extract_pdf
from app.ingestion.labs.parser_utils import extract_numeric_value
from app.domain.labs.normalization import (
    resolve_canonical_test,
    standardize_test_name,
)

import hashlib

def insert_rows(rows):
    db = SessionLocal()
    inserted = 0
    updated = 0
    skipped = 0

    for row in rows:
        dedupe_hash = generate_dedupe_hash(row)
        row_numeric = _parse_numeric_for_insert(row.get("result_value_text"))
        row_lab_date = parse_date_safe(row["lab_date"])

        # Reconcile historical stale rows (e.g., prior runs using reported date).
        matching_rows = (
            db.query(LabResult)
            .filter(
                LabResult.source_test_name == row["source_test_name"],
                LabResult.result_value_text == row["result_value_text"],
                LabResult.unit == row["unit"],
            )
            .all()
        )
        for mr in matching_rows:
            changed = False
            if row_lab_date and mr.lab_date != row_lab_date:
                conflict = db.query(LabResult).filter(
                    LabResult.dedupe_hash == dedupe_hash,
                    LabResult.id != mr.id,
                ).first()
                if conflict:
                    if conflict.result_value_numeric is None and row_numeric is not None:
                        conflict.result_value_numeric = row_numeric
                        updated += 1
                    db.delete(mr)
                    updated += 1
                    continue
                mr.lab_date = row_lab_date
                changed = True
            if mr.result_value_numeric is None and row_numeric is not None:
                mr.result_value_numeric = row_numeric
                changed = True
            if changed:
                mr.dedupe_hash = dedupe_hash
                updated += 1

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
            lab_date=row_lab_date,
            source_test_name=row["source_test_name"],
            result_value_text=row["result_value_text"],
            result_value_numeric=row_numeric,
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
    print(f"Updated: {updated}")
    print(f"Skipped (duplicates): {skipped}")


def _parse_numeric_for_insert(value_text):
    text = (value_text or "").strip()
    if not text:
        return None
    if text.startswith("<") or text.startswith(">"):
        return None
    return extract_numeric_value(text)

def parse_date_safe(date_str):
    try:
        return datetime.strptime(date_str, "%m/%d/%y").date()
    except:
        return None

def generate_dedupe_hash(row: dict) -> str:
    key = f"{row['lab_date']}|{row['source_test_name']}|{row['result_value_text']}|{row['unit']}"
    return hashlib.sha256(key.encode()).hexdigest()


def main():
    pdf_path = Path(sys.argv[1]).resolve()

    # reuse debug extractor but capture output instead of printing
    rows = extract_pdf(pdf_path)  # we will tweak this next if needed

    insert_rows(rows)


if __name__ == "__main__":
    main()