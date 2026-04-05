import re
import argparse
from pathlib import Path
from typing import List, Dict, Optional

import fitz  # PyMuPDF


HEADER_STOP_TOKENS = {
    "COMMENT:",
    "TEST NAME",
    "RESULT",
    "UNIT",
    "RANGE",
    "REFERENCE",
    "STATUS",
    "DATE/TM LAB",
}

FOOTER_START_TOKENS = {
    "CONTINUED ON NEXT PAGE",
    "PERFORMING LABORATORY INFORMATION",
    "PERFORMING SITE(S)",
    "REPORT COMPLETE",
}

ROW_END_STATUSES = {"FINAL", "CANCEL", "PRELIMINARY", "CORRECTED"}

IGNORE_EXACT = {
    "TRUMED, INC",
    "PATIENT NAME:",
    "PATIENT DOB:",
    "GENDER:  M",
    "PATIENT ID:",
    "ACCESSION#:",
    "ORD PHYS:",
    "LAB ACCOUNT#:",
    "RECEIVED:",
    "LAB ACCESSION#:",
    "REPORTED:",
    "COLLECTED:",
    "COMMENT:",
    "TEST NAME",
    "RESULT",
    "UNIT",
    "RANGE",
    "REFERENCE",
    "STATUS",
    "DATE/TM LAB",
    "LAB",
    "PERFORMING SITE(S)",
    "DLO",
    "Z3E",
    "98",
    "99",
    "MDF",
    "NOTE 1",
    "SEE NOTE 1",
    "SEE NOTE:",
    "(NOTE)",
    "EXTRA",
    "RISK:",
    "REFERENCE RANGE",
}

IGNORE_PREFIXES = (
    "TRUMED, INC",
    "PATIENT NAME",
    "PATIENT DOB",
    "GENDER",
    "PATIENT ID",
    "ACCESSION#",
    "ORD PHYS",
    "LAB ACCOUNT#",
    "RECEIVED",
    "LAB ACCESSION#",
    "COLLECTED",
    "REPORTED",
    "COMMENT",
    "CONTINUED ON NEXT PAGE",
    "PERFORMING LABORATORY INFORMATION",
    "DIAGNOSTIC LABORATORY OF OKLAHOMA",
    "MEDFUSION-MEDFUSION",
    "QUEST DIAGNOSTICS/NICHOLS",
    "CLEVELAND HEARTLAB",
    "HTTP://",
    "HTTPS://",
    "FOR ADDITIONAL INFORMATION",
    "THIS TEST WAS DEVELOPED",
    "CHARACTERISTICS HAVE BEEN DETERMINED",
    "IT HAS NOT BEEN CLEARED",
    "USED FOR CLINICAL PURPOSES",
    "REFERENCE RANGE ESTABLISHED",
    "PLEASE NOTE:",
    "FOR THE PURPOSE OF SCREENING",
    "CURRENTLY, NO CONSENSUS EXISTS",
    "ACCORDING TO AMERICAN DIABETES ASSOCIATION",
    "JACOBSON",
    "CUCHEL",
    "MARTIN SS",
    "PEARSON TA",
    "SELHUB J",
    "JELLINGER PS",
    "AM HEART ASSOC",
    "CLINICAL LIPIDOLOGY",
    "STANDARDS OF MEDICAL CARE",
)

UNIT_PATTERN = re.compile(
    r"""
    ^
    (?:
        %|
        \(calc\)|
        [A-Za-zµμ][A-Za-z0-9µμ/\-\.\^]*|
        [A-Za-zµμ][A-Za-z0-9µμ/\-\.\^ ]*[A-Za-z0-9µμ/\-\.\^]
    )
    $
    """,
    re.VERBOSE,
)

NUMERIC_PATTERN = re.compile(r"^[<>]?\s*-?\d+(?:\.\d+)?$")
DATE_PATTERN = re.compile(r"(\d{2}/\d{2}/\d{2})")
TIME_PATTERN = re.compile(r"^\d{1,2}:\d{2}$")


def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def is_blank(line: str) -> bool:
    return not normalize(line)


def is_numeric_value(line: str) -> bool:
    s = normalize(line)
    if s in {"NOT RESULTED", "SEE NOTE:", "SEE NOTE"}:
        return False
    return bool(NUMERIC_PATTERN.match(s))


def is_unit(line: str) -> bool:
    s = normalize(line)
    u = s.upper()

    if not s:
        return False

    # never treat these as units
    if u in {
        "FINAL", "CANCEL", "PRELIMINARY", "CORRECTED",
        "HIGH", "LOW",
        "NOT RESULTED", "SEE NOTE:", "SEE NOTE",
    }:
        return False

    if DATE_PATTERN.match(s) or TIME_PATTERN.match(s):
        return False

    if s.startswith("Reference Range"):
        return False

    # known valid unit-style values in these lab PDFs
    valid_units = {
        "%", "(calc)", "/100 WBC",
        "ng/mL", "pg/mL", "mg/dL", "mg/L", "g/dL",
        "mmol/L", "mIU/L", "mcg/dL", "uIU/mL", "umol/L",
        "U/L", "fL", "pg", "SD",
        "Thousand/uL", "Million/uL", "cells/uL",
        "pmol/L", "nmol/min/mL", "mL/min/1.73m2",
        "g/dL (calc)", "mg/dL (calc)",
    }

    return s in valid_units


def is_reference_range(line: str) -> bool:
    s = normalize(line)
    return bool(
        re.match(r"^[<>]?\s*\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?$", s)
        or re.match(r"^[<>]=?\s*\d+(?:\.\d+)?$", s, re.IGNORECASE)
        or re.match(r"^[<>]\s*OR\s*=\s*\d+(?:\.\d+)?$", s, re.IGNORECASE)
        or re.match(r"^\d+(?:\.\d+)?\s*-\s*\d+(?:\.\d+)?$", s)
    )


def is_status(line: str) -> bool:
    return normalize(line).upper() in ROW_END_STATUSES


def is_lab_code(line: str) -> bool:
    s = normalize(line).upper()
    return s in {"DLO", "Z3E", "98", "99"}


def looks_like_test_name(line: str) -> bool:
    s = normalize(line)
    u = s.upper()

    if not s:
        return False

    if u in IGNORE_EXACT:
        return False

    if any(u.startswith(prefix) for prefix in IGNORE_PREFIXES):
        return False

    if DATE_PATTERN.match(s) or TIME_PATTERN.match(s):
        return False

    if is_numeric_value(s) or is_reference_range(s) or is_status(s) or is_lab_code(s):
        return False

    # never allow obvious unit-only lines as test names
    if is_unit(s):
        return False

    # obvious non-test junk
    if re.search(r"\b(OK \d{5}|TX \d{5}|CA \d{5}|OH \d{5})\b", s):
        return False
    if "STREET" in u or "HIGHWAY" in u or "SUITE" in u:
        return False
    if u.startswith("(") or u.startswith("HTTP"):
        return False
    if len(s) < 2:
        return False

    return True


def extract_page_lines(page) -> List[str]:
    blocks = page.get_text("blocks")
    blocks = sorted(blocks, key=lambda b: (round(b[1], 1), round(b[0], 1)))

    lines: List[str] = []
    for block in blocks:
        text = block[4]
        for raw_line in text.splitlines():
            clean = normalize(raw_line)
            if clean:
                lines.append(clean)
    return lines


def extract_lab_date(lines: List[str]) -> Optional[str]:
    collected = None
    reported = None

    for i, line in enumerate(lines):
        if line.upper().startswith("COLLECTED:"):
            m = DATE_PATTERN.search(line)
            if m:
                collected = m.group(1)
            elif i + 1 < len(lines):
                m = DATE_PATTERN.search(lines[i + 1])
                if m:
                    collected = m.group(1)

        if line.upper().startswith("REPORTED:"):
            m = DATE_PATTERN.search(line)
            if m:
                reported = m.group(1)
            elif i + 1 < len(lines):
                m = DATE_PATTERN.search(lines[i + 1])
                if m:
                    reported = m.group(1)

    return collected or reported


def trim_to_results_section(lines: List[str]) -> List[str]:
    start_idx = None
    for i, line in enumerate(lines):
        if normalize(line).upper() == "DATE/TM LAB":
            start_idx = i + 1
            break

    if start_idx is None:
        return []

    trimmed = []
    for line in lines[start_idx:]:
        u = normalize(line).upper()
        if any(u.startswith(token) for token in FOOTER_START_TOKENS):
            break
        trimmed.append(line)

    return trimmed


def parse_rows(lines: List[str], page_lab_date: Optional[str]) -> List[Dict]:
    results = []
    i = 0
    n = len(lines)

    SECTION_HEADER_PREFIXES = (
        "LIPID PANEL",
        "COMPREHENSIVE METABOLIC PANEL",
        "CBC (INCLUDES DIFF/PLT)",
        "CARDIO IQ(",
        "TESTOSTERONE, FREE (DIALYSIS) AND TOTAL,MS",
        "ADMA/SDMA",
    )

    BAD_TEST_PREFIXES = (
        "THIS TEST WAS DEVELOPED",
        "CHARACTERISTICS HAVE BEEN DETERMINED",
        "IT HAS NOT BEEN CLEARED",
        "USED FOR CLINICAL PURPOSES",
        "REFERENCE RANGE",
        "RISK:",
        "OPTIMAL ",
        "MODERATE ",
        "ADULT CARDIOVASCULAR EVENT RISK",
        "CUT POINTS",
        "STUDIES PERFORMED",
        "IF A NON-FASTING SPECIMEN",
        "JACOBSON",
        "CUCHEL",
        "MARTIN SS",
        "FOR QUESTIONS ABOUT TESTING",
        "THERAPEUTIC TARGET",
        "FASTING REFERENCE INTERVAL",
        "NOT REPORTED:",
        "HOMOCYSTEINE IS INCREASED",
        "FOR ADDITIONAL INFORMATION",
        "PLEASE NOTE:",
        "THE TOTAL PSA VALUE",
        "THIS TEST WAS PERFORMED",
        "VITAMIN D STATUS",
        "DEFICIENCY:",
        "INSUFFICIENCY:",
        "OPTIMAL:",
        "FOR THE PURPOSE OF SCREENING",
        "CURRENTLY, NO CONSENSUS EXISTS",
        "ACCORDING TO AMERICAN DIABETES ASSOCIATION",
        "STANDARDS OF MEDICAL CARE",
        "SEE NOTE",
        "NOTE 1",
        "NOTE",
        "(NOTE)",
        "HTTP://",
        "HTTPS://",
        "(HTTP://",
        "(HTTPS://",
        "AMERICAN HEART ASSOCIATION",
        "PEARSON TA",
        "SELHUB J",
        "JELLINGER PS",
        "VALUE, SHOULD NOT BE INTERPRETED",
        "(THIS LINK IS BEING PROVIDED",
        "(REFERENCE:",
        "---THE FOLLOWING RESULTS WERE PREVIOUSLY REPORTED",
    )

    def is_section_header(s: str) -> bool:
        u = normalize(s).upper()
        return any(u.startswith(prefix) for prefix in SECTION_HEADER_PREFIXES)

    def is_bad_test_name(s: str) -> bool:
        u = normalize(s).upper()
        if not u:
            return True
        if any(u.startswith(prefix) for prefix in BAD_TEST_PREFIXES):
            return True
        if u in {"EXTRA", "SPECIMEN TYPE RECEIVED:", "COMMENT(S)"}:
            return True
        return False

    while i < n:
        line = normalize(lines[i])

        if not looks_like_test_name(line) or is_bad_test_name(line) or is_section_header(line):
            i += 1
            continue

        test_name = line
        j = i + 1

        # Common pattern: test name repeated twice
        if j < n and normalize(lines[j]).upper() == test_name.upper():
            j += 1

        # Look for value within next 2 lines only
        if j >= n or not is_numeric_value(lines[j]):
            i += 1
            continue

        result_value = normalize(lines[j])
        j += 1

        unit = None
        reference_range = None
        abnormal_flag = None
        result_status = None
        result_date = page_lab_date
        result_time = None
        lab_code = None

        # unit required
        if j < n and is_unit(lines[j]):
            unit = normalize(lines[j])
            j += 1
        else:
            i += 1
            continue

        # optional range
        if j < n and is_reference_range(lines[j]):
            reference_range = normalize(lines[j])
            j += 1

        # optional flag
        if j < n and normalize(lines[j]).upper() in {"HIGH", "LOW"}:
            abnormal_flag = normalize(lines[j]).upper()
            j += 1

        # required tail: status/date/time/lab
        if j < n and is_status(lines[j]):
            result_status = normalize(lines[j]).upper()
            j += 1
        else:
            i += 1
            continue

        if j < n and DATE_PATTERN.match(normalize(lines[j])):
            result_date = DATE_PATTERN.match(normalize(lines[j])).group(1)
            j += 1
        else:
            i += 1
            continue

        if j < n and TIME_PATTERN.match(normalize(lines[j])):
            result_time = normalize(lines[j])
            j += 1
        else:
            i += 1
            continue

        if j < n and is_lab_code(lines[j]):
            lab_code = normalize(lines[j])
            j += 1
        else:
            i += 1
            continue

        # final junk filters
        bad_exact = {
            "LIPID PANEL, STANDARD",
            "COMPREHENSIVE METABOLIC PANEL",
            "CBC (INCLUDES DIFF/PLT)",
            "CBC (INCLUDES DIFF/PLT) (CONTINUED FROM PREVIOUS PAGE)",
            "TESTOSTERONE, FREE (DIALYSIS) AND TOTAL,MS",
            "CARDIO IQ(R) MYELOPEROXIDASE (MPO)",
            "CARDIO IQ(R) LP PLA2 ACTIVITY",
            "ADMA/SDMA",
        }
        if test_name.upper() in bad_exact:
            i += 1
            continue

        results.append(
            {
                "lab_date": result_date,
                "source_test_name": test_name,
                "result_value_text": result_value,
                "unit": unit,
                "reference_range": reference_range,
                "abnormal_flag": abnormal_flag,
                "status": result_status,
                "result_time": result_time,
                "lab_code": lab_code,
            }
        )

        i = j

    return results


def print_page_debug(page_num: int, page_lab_date: Optional[str], page_lines: List[str], parsed_rows: List[Dict]) -> None:
    print("\n" + "#" * 100)
    print(f"PAGE {page_num}")
    print(f"PAGE LAB DATE CANDIDATE: {page_lab_date}")
    print("#" * 100)

    print("\n--- CLEANED RESULT-SECTION LINES START ---\n")
    for line in page_lines[:250]:
        print(line)
    print("\n--- CLEANED RESULT-SECTION LINES END ---\n")

    print(f"Structured rows found on page {page_num}: {len(parsed_rows)}\n")
    for idx, row in enumerate(parsed_rows, start=1):
        print(f"[{idx}]")
        print(f"  lab_date         : {row['lab_date']}")
        print(f"  source_test_name : {row['source_test_name']}")
        print(f"  result_value_text: {row['result_value_text']}")
        print(f"  unit             : {row['unit']}")
        print(f"  reference_range  : {row['reference_range']}")
        print(f"  abnormal_flag    : {row['abnormal_flag']}")
        print(f"  status           : {row['status']}")
        print(f"  result_time      : {row['result_time']}")
        print(f"  lab_code         : {row['lab_code']}")
        print()


def extract_pdf(pdf_path: Path) -> None:
    if not pdf_path.exists():
        raise FileNotFoundError(f"File not found: {pdf_path}")

    doc = fitz.open(pdf_path)

    print("=" * 100)
    print(f"PDF: {pdf_path}")
    print(f"Pages: {doc.page_count}")
    print("=" * 100)

    all_rows = []

    for page_index in range(doc.page_count):
        page = doc.load_page(page_index)
        raw_lines = extract_page_lines(page)
        page_lab_date = extract_lab_date(raw_lines)
        result_lines = trim_to_results_section(raw_lines)
        parsed_rows = parse_rows(result_lines, page_lab_date)

        print_page_debug(page_index + 1, page_lab_date, result_lines, parsed_rows)
        all_rows.extend(parsed_rows)

    print("\n" + "=" * 100)
    print("SUMMARY")
    print("=" * 100)
    print(f"Total structured rows found: {len(all_rows)}\n")

    for idx, row in enumerate(all_rows[:80], start=1):
        print(
            f"{idx:02d}. "
            f"date={row['lab_date']} | "
            f"test={row['source_test_name']} | "
            f"value={row['result_value_text']} | "
            f"unit={row['unit']} | "
            f"range={row['reference_range']} | "
            f"flag={row['abnormal_flag']} | "
            f"status={row['status']} | "
            f"lab={row['lab_code']}"
        )

    doc.close()
    return all_rows

def main():
    parser = argparse.ArgumentParser(description="Debug structured extraction from Quest/DLO lab PDFs.")
    parser.add_argument("pdf_path", help="Path to one PDF file")
    args = parser.parse_args()

    pdf_path = Path(args.pdf_path).resolve()
    extract_pdf(pdf_path)


if __name__ == "__main__":
    main()