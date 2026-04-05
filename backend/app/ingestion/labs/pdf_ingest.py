import sys
import os
import re
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime
import hashlib
import fitz  # PyMuPDF

from app.db.database import SessionLocal
from app.db.models import LabResult
from app.domain.labs.normalization import resolve_canonical_test, standardize_test_name

# --- PDF Extraction Logic (Inlined from old debug script) ---

HEADER_STOP_TOKENS = {"COMMENT:", "TEST NAME", "RESULT", "UNIT", "RANGE", "REFERENCE", "STATUS", "DATE/TM LAB"}
FOOTER_START_TOKENS = {"CONTINUED ON NEXT PAGE", "PERFORMING LABORATORY INFORMATION", "PERFORMING SITE(S)", "REPORT COMPLETE"}
ROW_END_STATUSES = {"FINAL", "CANCEL", "PRELIMINARY", "CORRECTED"}

IGNORE_EXACT = {
    "TRUMED, INC", "PATIENT NAME:", "PATIENT DOB:", "GENDER:  M", "PATIENT ID:", "ACCESSION#:", "ORD PHYS:",
    "LAB ACCOUNT#:", "RECEIVED:", "LAB ACCESSION#:", "REPORTED:", "COLLECTED:", "COMMENT:", "TEST NAME", 
    "RESULT", "UNIT", "RANGE", "REFERENCE", "STATUS", "DATE/TM LAB", "LAB", "PERFORMING SITE(S)", "DLO", 
    "Z3E", "98", "99", "MDF", "NOTE 1", "SEE NOTE 1", "SEE NOTE:", "(NOTE)", "EXTRA", "RISK:", "REFERENCE RANGE"
}

IGNORE_PREFIXES = (
    "TRUMED, INC", "PATIENT NAME", "PATIENT DOB", "GENDER", "PATIENT ID", "ACCESSION#", "ORD PHYS", "LAB ACCOUNT#",
    "RECEIVED", "LAB ACCESSION#", "COLLECTED", "REPORTED", "COMMENT", "CONTINUED ON NEXT PAGE", 
    "PERFORMING LABORATORY INFORMATION", "DIAGNOSTIC LABORATORY OF OKLAHOMA", "MEDFUSION-MEDFUSION", 
    "QUEST DIAGNOSTICS/NICHOLS", "CLEVELAND HEARTLAB", "HTTP://", "HTTPS://", "FOR ADDITIONAL INFORMATION", 
    "THIS TEST WAS DEVELOPED", "CHARACTERISTICS HAVE BEEN DETERMINED", "IT HAS NOT BEEN CLEARED", 
    "USED FOR CLINICAL PURPOSES", "REFERENCE RANGE ESTABLISHED", "PLEASE NOTE:", "FOR THE PURPOSE OF SCREENING", 
    "CURRENTLY, NO CONSENSUS EXISTS", "ACCORDING TO AMERICAN DIABETES ASSOCIATION", "JACOBSON", "CUCHEL", 
    "MARTIN SS", "PEARSON TA", "SELHUB J", "JELLINGER PS", "AM HEART ASSOC", "CLINICAL LIPIDOLOGY", "STANDARDS OF MEDICAL CARE"
)

UNIT_PATTERN = re.compile(r"^(?:%|\(calc\)|[A-Za-zµμ][A-Za-z0-9µμ/\-\.\^]*|[A-Za-zµμ][A-Za-z0-9µμ/\-\.\^ ]*[A-Za-z0-9µμ/\-\.\^])$", re.VERBOSE)
NUMERIC_PATTERN = re.compile(r"^[<>]?\s*-?\d+(?:\.\d+)?$")
DATE_PATTERN = re.compile(r"(\d{2}/\d{2}/\d{2})")
TIME_PATTERN = re.compile(r"^\d{1,2}:\d{2}$")

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()

def is_numeric_value(line: str) -> bool:
    s = normalize(line)
    if s in {"NOT RESULTED", "SEE NOTE:", "SEE NOTE"}: return False
    return bool(NUMERIC_PATTERN.match(s))

def is_unit(line: str) -> bool:
    s = normalize(line)
    u = s.upper()
    if not s: return False
    if u in {"FINAL", "CANCEL", "PRELIMINARY", "CORRECTED", "HIGH", "LOW", "NOT RESULTED", "SEE NOTE:", "SEE NOTE"}: return False
    if DATE_PATTERN.match(s) or TIME_PATTERN.match(s): return False
    if s.startswith("Reference Range"): return False
    valid_units = {"%", "(calc)", "/100 WBC", "ng/mL", "pg/mL", "mg/dL", "mg/L", "g/dL", "mmol/L", "mIU/L", "mcg/dL", "uIU/mL", "umol/L", "U/L", "fL", "pg", "SD", "Thousand/uL", "Million/uL", "cells/uL", "pmol/L", "nmol/min/mL", "mL/min/1.73m2", "g/dL (calc)", "mg/dL (calc)"}
    return s in valid_units

def is_reference_range(line: str) -> bool:
    s = normalize(line)
    return bool(
        re.match(r"^[<>]?\s*\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?$", s) or 
        re.match(r"^[<>]=?\s*\d+(?:\.\d+)?$", s, re.IGNORECASE) or 
        re.match(r"^[<>]\s*OR\s*=\s*\d+(?:\.\d+)?$", s, re.IGNORECASE) or 
        re.match(r"^\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?$", s)
    )

def is_status(line: str) -> bool:
    return normalize(line).upper() in ROW_END_STATUSES

def is_lab_code(line: str) -> bool:
    return normalize(line).upper() in {"DLO", "Z3E", "98", "99"}

def looks_like_test_name(line: str) -> bool:
    s = normalize(line)
    u = s.upper()
    if not s or u in IGNORE_EXACT or any(u.startswith(p) for p in IGNORE_PREFIXES): return False
    if DATE_PATTERN.match(s) or TIME_PATTERN.match(s): return False
    if is_numeric_value(s) or is_reference_range(s) or is_status(s) or is_lab_code(s) or is_unit(s): return False
    if re.search(r"\b(OK \d{5}|TX \d{5}|CA \d{5}|OH \d{5})\b", s) or "STREET" in u or "HIGHWAY" in u or "SUITE" in u: return False
    if u.startswith("(") or u.startswith("HTTP") or len(s) < 2: return False
    return True

def extract_page_lines(page) -> List[str]:
    blocks = sorted(page.get_text("blocks"), key=lambda b: (round(b[1], 1), round(b[0], 1)))
    lines = []
    for block in blocks:
        for raw_line in block[4].splitlines():
            clean = normalize(raw_line)
            if clean: lines.append(clean)
    return lines

def extract_lab_date(lines: List[str]) -> Optional[str]:
    collected, reported = None, None
    for i, line in enumerate(lines):
        if line.upper().startswith("COLLECTED:"):
            m = DATE_PATTERN.search(line) or (DATE_PATTERN.search(lines[i+1]) if i+1 < len(lines) else None)
            if m: collected = m.group(1)
        if line.upper().startswith("REPORTED:"):
            m = DATE_PATTERN.search(line) or (DATE_PATTERN.search(lines[i+1]) if i+1 < len(lines) else None)
            if m: reported = m.group(1)
    return collected or reported

def trim_to_results_section(lines: List[str]) -> List[str]:
    start_idx = next((i + 1 for i, line in enumerate(lines) if normalize(line).upper() == "DATE/TM LAB"), None)
    if start_idx is None: return []
    trimmed = []
    for line in lines[start_idx:]:
        if any(normalize(line).upper().startswith(token) for token in FOOTER_START_TOKENS): break
        trimmed.append(line)
    return trimmed

def parse_rows(lines: List[str], page_lab_date: Optional[str]) -> List[Dict]:
    results, i, n = [], 0, len(lines)
    SECTION_HEADER_PREFIXES = ("LIPID PANEL", "COMPREHENSIVE METABOLIC PANEL", "CBC (INCLUDES DIFF/PLT)", "CARDIO IQ(", "TESTOSTERONE, FREE (DIALYSIS) AND TOTAL,MS", "ADMA/SDMA")
    BAD_TEST_PREFIXES = ("THIS TEST WAS DEVELOPED", "CHARACTERISTICS HAVE BEEN DETERMINED", "IT HAS NOT BEEN CLEARED", "USED FOR CLINICAL PURPOSES", "REFERENCE RANGE", "RISK:", "OPTIMAL ", "MODERATE ", "ADULT CARDIOVASCULAR EVENT RISK", "CUT POINTS", "STUDIES PERFORMED", "IF A NON-FASTING SPECIMEN", "JACOBSON", "CUCHEL", "MARTIN SS", "FOR QUESTIONS ABOUT TESTING", "THERAPEUTIC TARGET", "FASTING REFERENCE INTERVAL", "NOT REPORTED:", "HOMOCYSTEINE IS INCREASED", "FOR ADDITIONAL INFORMATION", "PLEASE NOTE:", "THE TOTAL PSA VALUE", "THIS TEST WAS PERFORMED", "VITAMIN D STATUS", "DEFICIENCY:", "INSUFFICIENCY:", "OPTIMAL:", "FOR THE PURPOSE OF SCREENING", "CURRENTLY, NO CONSENSUS EXISTS", "ACCORDING TO AMERICAN DIABETES ASSOCIATION", "STANDARDS OF MEDICAL CARE", "SEE NOTE", "NOTE 1", "NOTE", "(NOTE)", "HTTP://", "HTTPS://", "(HTTP://", "(HTTPS://", "AMERICAN HEART ASSOCIATION", "PEARSON TA", "SELHUB J", "JELLINGER PS", "VALUE, SHOULD NOT BE INTERPRETED", "(THIS LINK IS BEING PROVIDED", "(REFERENCE:", "---THE FOLLOWING RESULTS WERE PREVIOUSLY REPORTED")

    while i < n:
        line = normalize(lines[i])
        u_line = line.upper()
        if not looks_like_test_name(line) or any(u_line.startswith(p) for p in SECTION_HEADER_PREFIXES) or any(u_line.startswith(p) for p in BAD_TEST_PREFIXES) or u_line in {"EXTRA", "SPECIMEN TYPE RECEIVED:", "COMMENT(S)"}:
            i += 1; continue
        
        test_name = line
        j = i + 1
        if j < n and normalize(lines[j]).upper() == test_name.upper(): j += 1
        if j >= n or not is_numeric_value(lines[j]): i += 1; continue
        
        result_value = normalize(lines[j])
        j += 1
        
        unit, reference_range, abnormal_flag, result_status, result_date, result_time, lab_code = None, None, None, None, page_lab_date, None, None
        if j < n and is_unit(lines[j]):
            unit = normalize(lines[j]); j += 1
        else:
            i += 1; continue
            
        if j < n and is_reference_range(lines[j]): reference_range = normalize(lines[j]); j += 1
        if j < n and normalize(lines[j]).upper() in {"HIGH", "LOW"}: abnormal_flag = normalize(lines[j]).upper(); j += 1
        
        if j < n and is_status(lines[j]):
            result_status = normalize(lines[j]).upper(); j += 1
        else:
            i += 1; continue
            
        if j < n and DATE_PATTERN.match(normalize(lines[j])): result_date = DATE_PATTERN.match(normalize(lines[j])).group(1); j += 1
        else: i += 1; continue
        
        if j < n and TIME_PATTERN.match(normalize(lines[j])): result_time = normalize(lines[j]); j += 1
        else: i += 1; continue
        
        if j < n and is_lab_code(lines[j]): lab_code = normalize(lines[j]); j += 1
        else: i += 1; continue
        
        if test_name.upper() not in {"LIPID PANEL, STANDARD", "COMPREHENSIVE METABOLIC PANEL", "CBC (INCLUDES DIFF/PLT)", "CBC (INCLUDES DIFF/PLT) (CONTINUED FROM PREVIOUS PAGE)", "TESTOSTERONE, FREE (DIALYSIS) AND TOTAL,MS", "CARDIO IQ(R) MYELOPEROXIDASE (MPO)", "CARDIO IQ(R) LP PLA2 ACTIVITY", "ADMA/SDMA"}:
            results.append({"lab_date": result_date, "source_test_name": test_name, "result_value_text": result_value, "unit": unit, "reference_range": reference_range, "abnormal_flag": abnormal_flag, "status": result_status, "result_time": result_time, "lab_code": lab_code})
        i = j
    return results

def extract_pdf(pdf_path: Path) -> List[Dict]:
    if not pdf_path.exists(): raise FileNotFoundError(f"File not found: {pdf_path}")
    doc = fitz.open(pdf_path)
    all_rows = []
    for page_index in range(doc.page_count):
        raw_lines = extract_page_lines(doc.load_page(page_index))
        page_lab_date = extract_lab_date(raw_lines)
        parsed_rows = parse_rows(trim_to_results_section(raw_lines), page_lab_date)
        all_rows.extend(parsed_rows)
    doc.close()
    return all_rows

# --- Insertion Logic ---

def parse_date_safe(date_str):
    try: return datetime.strptime(date_str, "%m/%d/%y").date()
    except: return None

def generate_dedupe_hash(row: dict) -> str:
    key = f"{row['lab_date']}|{row['source_test_name']}|{row['result_value_text']}|{row['unit']}"
    return hashlib.sha256(key.encode()).hexdigest()

def insert_rows(rows):
    db = SessionLocal()
    inserted, skipped = 0, 0

    for row in rows:
        dedupe_hash = generate_dedupe_hash(row)
        if db.query(LabResult).filter_by(dedupe_hash=dedupe_hash).first():
            skipped += 1
            continue

        resolved = resolve_canonical_test(db, row["source_test_name"], source_scope="PDF")
        
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

def process_pdf_file(pdf_filepath: str):
    pdf_path = Path(pdf_filepath).resolve()
    rows = extract_pdf(pdf_path)
    insert_rows(rows)
