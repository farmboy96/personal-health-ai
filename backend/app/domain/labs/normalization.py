import re
from typing import Optional, Dict

from app.db.models import LabTestAlias, LabTestCatalog


def standardize_test_name(raw_name: str) -> str:
    if not raw_name:
        return ""

    s = raw_name.upper().strip()
    s = s.replace("-", " ")
    s = s.replace("/", " ")
    s = s.replace(",", " ")
    s = re.sub(r"[()]", " ", s)
    s = re.sub(r"[^A-Z0-9\s%]", " ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s


def apply_fallback_rules(std_name: str) -> Optional[str]:
    if not std_name:
        return None

    if std_name == "GLUCOSE":
        return "GLUCOSE"

    if std_name in ("CHOLESTEROL TOTAL", "TOTAL CHOLESTEROL"):
        return "TOTAL_CHOLESTEROL"

    if std_name in ("HDL CHOLESTEROL", "HDL"):
        return "HDL"

    if std_name in ("LDL CHOLESTEROL", "LDL CALC", "LDL CALCULATED", "LDL"):
        return "LDL"

    if std_name == "TRIGLYCERIDES":
        return "TRIGLYCERIDES"

    if std_name in ("HEMOGLOBIN A1C", "HGB A1C", "A1C"):
        return "A1C"

    return None


def resolve_canonical_test(session, raw_name: str, source_scope: str = "ANY") -> Optional[Dict[str, str]]:
    std_name = standardize_test_name(raw_name)
    if not std_name:
        return None

    alias = (
        session.query(LabTestAlias)
        .filter(LabTestAlias.normalized_lookup == std_name)
        .first()
    )

    canonical_code = alias.canonical_code if alias else apply_fallback_rules(std_name)

    if not canonical_code:
        return None

    catalog = (
        session.query(LabTestCatalog)
        .filter(LabTestCatalog.canonical_code == canonical_code)
        .first()
    )

    if not catalog:
        return {
            "canonical_test_code": canonical_code,
            "canonical_test_name": canonical_code,
            "test_category": None,
            "panel_name": None,
        }

    return {
        "canonical_test_code": catalog.canonical_code,
        "canonical_test_name": catalog.display_name,
        "test_category": catalog.category,
        "panel_name": catalog.panel_name,
    }