import json
import re
from datetime import datetime

import pandas as pd
from sqlalchemy.dialects.sqlite import insert
from app.ingestion.labs.parser_utils import extract_numeric_value
from sqlalchemy.orm import Session

from app.db.models import ImportRun, LabResult, LabTestMaster, SourceFile
from app.ingestion.common.file_hashing import generate_lab_dedupe_hash
from app.services.labs.lab_name_normalizer import normalize_lab_name


SECTION_HEADER_NAMES = {
    "Hormone Panel",
    "Metabolic/Inflammation",
    "Thyroid Panel",
    "Cholesterol Panel",
}


def is_section_header(test_name: str) -> bool:
    if not test_name:
        return False
    return test_name.strip() in SECTION_HEADER_NAMES


def extract_unit_from_test_name(test_name: str) -> str | None:
    if not test_name:
        return None

    match = re.search(r"\(([^)]+)\)\s*$", test_name.strip())
    if not match:
        return None

    candidate = match.group(1).strip()
    if not candidate:
        return None

    # Only treat trailing parentheses as units when they actually look like units.
    # This blocks things like "(TSH)" while keeping "(ng/mL)", "(pg/mL)", "(mIU/mL)".
    unit_indicators = ["/", "%", "mmol", "mol", "g/dl", "mg/dl", "ng", "pg", "ug", "miu", "iu", "fl"]
    candidate_lower = candidate.lower()

    if any(ind in candidate_lower for ind in unit_indicators):
        return candidate

    return None


def normalize_reference_part(value) -> str | None:
    if pd.isna(value):
        return None

    text = str(value).strip()
    if not text:
        return None

    text = re.sub(r"\s+", "", text)
    return text


def build_reference_range(low_val, high_val) -> str | None:
    low = normalize_reference_part(low_val)
    high = normalize_reference_part(high_val)

    if low and high:
        return f"{low} - {high}"
    if low:
        return low
    if high:
        return high
    return None


def extract_numeric_and_flag(val):
    if pd.isna(val):
        return None, None, None

    raw_text = str(val).strip()
    if not raw_text:
        return None, None, None

    flag = None
    upper_text = raw_text.upper()

    if upper_text.endswith(" L"):
        flag = "L"
        raw_text = raw_text[:-2].strip()
    elif upper_text.endswith(" H"):
        flag = "H"
        raw_text = raw_text[:-2].strip()
    elif upper_text.endswith("L") and re.search(r"\dL$", upper_text) is None:
        flag = "L"
        raw_text = raw_text[:-1].strip()
    elif upper_text.endswith("H"):
        flag = "H"
        raw_text = raw_text[:-1].strip()

    match = re.search(r"[-+]?\d*\.\d+|[-+]?\d+", raw_text)
    if match:
        num_val = float(match.group())
        result_text = None if match.group() == raw_text else raw_text
        return num_val, result_text, flag

    return None, raw_text, flag


def process_excel_file(
    db: Session,
    filepath: str,
    source_file: SourceFile,
    import_run: ImportRun,
):
    df = pd.read_excel(filepath, header=None)

    # Locked to the known static workbook structure
    header_row = 2
    data_start = 3

    header = df.iloc[header_row]

    # Col 0 = test name, 1 = low, 2 = high, 3+ = dates
    date_cols = []
    for col_idx in range(3, len(header)):
        if isinstance(header[col_idx], (datetime, pd.Timestamp)):
            date_cols.append((col_idx, header[col_idx]))

    if not date_cols:
        raise ValueError("No date columns found in expected header row.")

    master_tests = {
        t.standard_name: t.id
        for t in db.query(LabTestMaster).all()
    }

    batch = []

    for row_idx in range(data_start, len(df)):
        test_name = df.iloc[row_idx, 0]

        if pd.isna(test_name):
            continue

        test_name = str(test_name).strip()
        if not test_name:
            continue

        if is_section_header(test_name):
            continue

        canonical = normalize_lab_name(test_name)
        if not canonical:
            import_run.records_skipped += 1
            continue

        unit_val = extract_unit_from_test_name(test_name)

        if canonical not in master_tests:
            new_test = LabTestMaster(
                standard_name=canonical,
                standard_unit=unit_val,
            )
            db.add(new_test)
            db.flush()
            master_tests[canonical] = new_test.id

        test_id = master_tests[canonical]

        low_val = df.iloc[row_idx, 1]
        high_val = df.iloc[row_idx, 2]
        reference_range = build_reference_range(low_val, high_val)

        for col_idx, col_date in date_cols:
            raw_val = df.iloc[row_idx, col_idx]

            if pd.isna(raw_val):
                continue

            lab_date = col_date.date()
            numeric = extract_numeric_value(raw_val)
            num_val, txt_val, flag = extract_numeric_and_flag(raw_val)
            if numeric is not None:
                num_val = numeric

            dedupe_hash = generate_lab_dedupe_hash(
                source_file_name=source_file.filename,
                lab_date=str(lab_date),
                source_test_name=test_name,
                value_str=str(raw_val),
                unit=unit_val,
            )

            payload = json.dumps({
                "test": test_name,
                "date": str(col_date),
                "value": str(raw_val),
                "low": None if pd.isna(low_val) else str(low_val),
                "high": None if pd.isna(high_val) else str(high_val),
            })

            batch.append({
                "source_file_id": source_file.id,
                "import_run_id": import_run.id,
                "test_id": test_id,
                "lab_date": lab_date,
                "source_test_name": test_name,
                "result_value_text": txt_val,
                "result_value_numeric": num_val,
                "unit": unit_val,
                "reference_range": reference_range,
                "abnormal_flag": flag,
                "dedupe_hash": dedupe_hash,
                "raw_payload": payload,
                "created_at": datetime.utcnow(),
            })

            import_run.records_seen += 1

    if batch:
        stmt = insert(LabResult).values(batch)
        stmt = stmt.on_conflict_do_nothing(index_elements=["dedupe_hash"])
        result = db.execute(stmt)

        added = result.rowcount if result.rowcount is not None else 0
        import_run.records_added += added
        import_run.records_skipped += max(0, len(batch) - added)

        db.commit()

    import_run.status = "success"
    import_run.end_time = datetime.utcnow()
    db.commit()

    print(f"[DONE] Seen={import_run.records_seen} Added={import_run.records_added}")