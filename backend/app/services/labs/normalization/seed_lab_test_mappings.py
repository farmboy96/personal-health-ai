import sys
import os

sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))

from app.db.database import SessionLocal
from app.db.models import LabTestCatalog, LabTestAlias
from app.domain.labs.normalization import standardize_test_name

CANONICAL_TESTS = {
    "GLUCOSE": {
        "display_name": "Glucose",
        "category": "CMP",
        "panel_name": "Comprehensive Metabolic Panel",
        "default_unit": "mg/dL",
        "aliases": ["GLUCOSE"],
    },
    "TOTAL_CHOLESTEROL": {
        "display_name": "Total Cholesterol",
        "category": "LIPID",
        "panel_name": "Lipid Panel",
        "default_unit": "mg/dL",
        "aliases": ["CHOLESTEROL, TOTAL", "CHOLESTEROL TOTAL", "TOTAL CHOLESTEROL"],
    },
    "HDL": {
        "display_name": "HDL Cholesterol",
        "category": "LIPID",
        "panel_name": "Lipid Panel",
        "default_unit": "mg/dL",
        "aliases": ["HDL CHOLESTEROL", "HDL"],
    },
    "LDL": {
        "display_name": "LDL Cholesterol",
        "category": "LIPID",
        "panel_name": "Lipid Panel",
        "default_unit": "mg/dL",
        "aliases": ["LDL-CHOLESTEROL", "LDL CHOLESTEROL", "LDL CALC", "LDL CALCULATED", "LDL"],
    },
    "TRIGLYCERIDES": {
        "display_name": "Triglycerides",
        "category": "LIPID",
        "panel_name": "Lipid Panel",
        "default_unit": "mg/dL",
        "aliases": ["TRIGLYCERIDES"],
    },
    "A1C": {
        "display_name": "Hemoglobin A1C",
        "category": "DIABETES",
        "panel_name": "Diabetes Monitoring",
        "default_unit": "%",
        "aliases": ["HEMOGLOBIN A1C", "HEMOGLOBIN A1c", "HGB A1C", "A1C"],
    },
    "TSH": {
        "display_name": "TSH",
        "category": "THYROID",
        "panel_name": "Thyroid",
        "default_unit": "mIU/L",
        "aliases": ["TSH"],
    },
    "FREE_T3": {
        "display_name": "Free T3",
        "category": "THYROID",
        "panel_name": "Thyroid",
        "default_unit": "pg/mL",
        "aliases": ["T3, FREE", "FREE T3"],
    },
    "PSA_TOTAL": {
        "display_name": "PSA Total",
        "category": "HORMONE",
        "panel_name": "Hormone / Prostate",
        "default_unit": "ng/mL",
        "aliases": ["PSA, TOTAL", "PSA TOTAL"],
    },
    "ESTRADIOL": {
        "display_name": "Estradiol",
        "category": "HORMONE",
        "panel_name": "Hormone",
        "default_unit": "pg/mL",
        "aliases": ["ESTRADIOL"],
    },
    "TESTOSTERONE_FREE": {
        "display_name": "Testosterone, Free",
        "category": "HORMONE",
        "panel_name": "Hormone",
        "default_unit": "pg/mL",
        "aliases": ["TESTOSTERONE, FREE", "FREE TESTOSTERONE"],
    },
    "VITAMIN_D_25_OH_TOTAL": {
        "display_name": "Vitamin D 25-OH Total",
        "category": "VITAMIN",
        "panel_name": "Vitamin",
        "default_unit": "ng/mL",
        "aliases": ["VITAMIN D,25-OH,TOTAL,IA", "VITAMIN D 25-OH TOTAL", "25-OH VITAMIN D"],
    },
    "FERRITIN": {
        "display_name": "Ferritin",
        "category": "IRON",
        "panel_name": "Iron Studies",
        "default_unit": "ng/mL",
        "aliases": ["FERRITIN"],
    },
    "DHEA_SULFATE": {
        "display_name": "DHEA Sulfate",
        "category": "HORMONE",
        "panel_name": "Hormone",
        "default_unit": "mcg/dL",
        "aliases": ["DHEA SULFATE", "DHEA-S"],
    },
    "HOMOCYSTEINE": {
        "display_name": "Homocysteine",
        "category": "CARDIO",
        "panel_name": "Cardio / Inflammation",
        "default_unit": "umol/L",
        "aliases": ["HOMOCYSTEINE"],
    },
    "HS_CRP": {
        "display_name": "hs-CRP",
        "category": "CARDIO",
        "panel_name": "Cardio / Inflammation",
        "default_unit": "mg/L",
        "aliases": ["HS CRP", "HS-CRP", "HIGH SENSITIVITY CRP"],
    },
    "RED_BLOOD_CELL_COUNT": {
        "display_name": "Red Blood Cell Count",
        "category": "CBC",
        "panel_name": "Complete Blood Count",
        "default_unit": "Million/uL",
        "aliases": ["RED BLOOD CELL COUNT", "RBC"],
    },
    "HEMOGLOBIN": {
        "display_name": "Hemoglobin",
        "category": "CBC",
        "panel_name": "Complete Blood Count",
        "default_unit": "g/dL",
        "aliases": ["HEMOGLOBIN"],
    },
    "HEMATOCRIT": {
        "display_name": "Hematocrit",
        "category": "CBC",
        "panel_name": "Complete Blood Count",
        "default_unit": "%",
        "aliases": ["HEMATOCRIT"],
    },
    "MCV": {
        "display_name": "MCV",
        "category": "CBC",
        "panel_name": "Complete Blood Count",
        "default_unit": "fL",
        "aliases": ["MCV"],
    },
    "MCH": {
        "display_name": "MCH",
        "category": "CBC",
        "panel_name": "Complete Blood Count",
        "default_unit": "pg",
        "aliases": ["MCH"],
    },
    "MCHC": {
        "display_name": "MCHC",
        "category": "CBC",
        "panel_name": "Complete Blood Count",
        "default_unit": "g/dL",
        "aliases": ["MCHC"],
    },
    "RDW": {
        "display_name": "RDW",
        "category": "CBC",
        "panel_name": "Complete Blood Count",
        "default_unit": "%",
        "aliases": ["RDW"],
    },
    "PLATELET_COUNT": {
        "display_name": "Platelet Count",
        "category": "CBC",
        "panel_name": "Complete Blood Count",
        "default_unit": "Thousand/uL",
        "aliases": ["PLATELET COUNT", "PLATELETS"],
    },
    "MPV": {
        "display_name": "MPV",
        "category": "CBC",
        "panel_name": "Complete Blood Count",
        "default_unit": "fL",
        "aliases": ["MPV"],
    },
    "NEUTROPHILS": {
        "display_name": "Neutrophils",
        "category": "CBC",
        "panel_name": "Complete Blood Count",
        "default_unit": "%",
        "aliases": ["NEUTROPHILS"],
    },
    "LYMPHOCYTES": {
        "display_name": "Lymphocytes",
        "category": "CBC",
        "panel_name": "Complete Blood Count",
        "default_unit": "%",
        "aliases": ["LYMPHOCYTES"],
    },
    "MONOCYTES": {
        "display_name": "Monocytes",
        "category": "CBC",
        "panel_name": "Complete Blood Count",
        "default_unit": "%",
        "aliases": ["MONOCYTES"],
    },
    "EOSINOPHILS": {
        "display_name": "Eosinophils",
        "category": "CBC",
        "panel_name": "Complete Blood Count",
        "default_unit": "%",
        "aliases": ["EOSINOPHILS"],
    },
    "BASOPHILS": {
        "display_name": "Basophils",
        "category": "CBC",
        "panel_name": "Complete Blood Count",
        "default_unit": "%",
        "aliases": ["BASOPHILS"],
    },
    "ABSOLUTE_NEUTROPHILS": {
        "display_name": "Absolute Neutrophils",
        "category": "CBC",
        "panel_name": "Complete Blood Count",
        "default_unit": "cells/uL",
        "aliases": ["ABSOLUTE NEUTROPHILS", "ABS NEUTROPHILS"],
    },
    "ABSOLUTE_LYMPHOCYTES": {
        "display_name": "Absolute Lymphocytes",
        "category": "CBC",
        "panel_name": "Complete Blood Count",
        "default_unit": "cells/uL",
        "aliases": ["ABSOLUTE LYMPHOCYTES", "ABS LYMPHOCYTES"],
    },
    "ABSOLUTE_MONOCYTES": {
        "display_name": "Absolute Monocytes",
        "category": "CBC",
        "panel_name": "Complete Blood Count",
        "default_unit": "cells/uL",
        "aliases": ["ABSOLUTE MONOCYTES", "ABS MONOCYTES"],
    },
    "ABSOLUTE_EOSINOPHILS": {
        "display_name": "Absolute Eosinophils",
        "category": "CBC",
        "panel_name": "Complete Blood Count",
        "default_unit": "cells/uL",
        "aliases": ["ABSOLUTE EOSINOPHILS", "ABS EOSINOPHILS"],
    },
    "ABSOLUTE_BASOPHILS": {
        "display_name": "Absolute Basophils",
        "category": "CBC",
        "panel_name": "Complete Blood Count",
        "default_unit": "cells/uL",
        "aliases": ["ABSOLUTE BASOPHILS", "ABS BASOPHILS"],
    },
    "TOTAL_CHOLESTEROL": {
    "display_name": "Total Cholesterol",
    "category": "LIPID",
    "panel_name": "Lipid Panel",
    "default_unit": "mg/dL",
    "aliases": [
        "CHOLESTEROL, TOTAL",
        "CHOLESTEROL TOTAL",
        "TOTAL CHOLESTEROL",
        "Cholesterol",
    ],
},
"HDL": {
    "display_name": "HDL Cholesterol",
    "category": "LIPID",
    "panel_name": "Lipid Panel",
    "default_unit": "mg/dL",
    "aliases": [
        "HDL CHOLESTEROL",
        "HDL",
        "Cholesterol, HDL",
    ],
},
"LDL": {
    "display_name": "LDL Cholesterol",
    "category": "LIPID",
    "panel_name": "Lipid Panel",
    "default_unit": "mg/dL",
    "aliases": [
        "LDL-CHOLESTEROL",
        "LDL CHOLESTEROL",
        "LDL CALC",
        "LDL CALCULATED",
        "LDL",
        "Cholesterol, LDL, calculated",
    ],
},
"CORONARY_RISK_RATIO": {
    "display_name": "Coronary Risk Ratio",
    "category": "LIPID",
    "panel_name": "Lipid Panel",
    "default_unit": None,
    "aliases": [
        "Coronary Risk Ratio",
        "CHOL/HDLC RATIO",
    ],
},
"NON_HDL_CHOLESTEROL": {
    "display_name": "Non-HDL Cholesterol",
    "category": "LIPID",
    "panel_name": "Lipid Panel",
    "default_unit": "mg/dL",
    "aliases": [
        "NON HDL CHOLESTEROL",
    ],
},
"TSH": {
    "display_name": "TSH",
    "category": "THYROID",
    "panel_name": "Thyroid",
    "default_unit": "mIU/L",
    "aliases": [
        "TSH",
        "Thyroid Stimulating Hormone (TSH)",
    ],
},
"FREE_T3": {
    "display_name": "Free T3",
    "category": "THYROID",
    "panel_name": "Thyroid",
    "default_unit": "pg/mL",
    "aliases": [
        "T3, FREE",
        "FREE T3",
        "T-3, Free (convert)",
    ],
},
"FREE_T4": {
    "display_name": "Free T4",
    "category": "THYROID",
    "panel_name": "Thyroid",
    "default_unit": "ng/dL",
    "aliases": [
        "T-4, Free",
        "FREE T4",
    ],
},
"VITAMIN_D_25_OH_TOTAL": {
    "display_name": "Vitamin D 25-OH Total",
    "category": "VITAMIN",
    "panel_name": "Vitamin",
    "default_unit": "ng/mL",
    "aliases": [
        "VITAMIN D,25-OH,TOTAL,IA",
        "VITAMIN D 25-OH TOTAL",
        "25-OH VITAMIN D",
        "Vitamin D, 25-OH",
    ],
},
"TESTOSTERONE_TOTAL": {
    "display_name": "Testosterone, Total",
    "category": "HORMONE",
    "panel_name": "Hormone",
    "default_unit": "ng/dL",
    "aliases": [
        "TESTOSTERONE, TOTAL",
        "Testosterone, Total (ng/dL)",
    ],
},
"TESTOSTERONE_FREE": {
    "display_name": "Testosterone, Free",
    "category": "HORMONE",
    "panel_name": "Hormone",
    "default_unit": "pg/mL",
    "aliases": [
        "TESTOSTERONE, FREE",
        "FREE TESTOSTERONE",
        "Testosterone, Free (pg/ml) convert",
    ],
},
"SHBG": {
    "display_name": "SHBG",
    "category": "HORMONE",
    "panel_name": "Hormone",
    "default_unit": "nmol/L",
    "aliases": [
        "SHBG",
        "SHBG (nmol/L)",
    ],
},
"PSA_TOTAL": {
    "display_name": "PSA Total",
    "category": "HORMONE",
    "panel_name": "Hormone / Prostate",
    "default_unit": "ng/mL",
    "aliases": [
        "PSA, TOTAL",
        "PSA TOTAL",
        "Prostate Specific Ag (PSA), Total (ng/mL)",
    ],
},
"ESTRADIOL": {
    "display_name": "Estradiol",
    "category": "HORMONE",
    "panel_name": "Hormone",
    "default_unit": "pg/mL",
    "aliases": [
        "ESTRADIOL",
        "Estradiol, High-Sensitivity (pg/mL)",
    ],
},
"INSULIN": {
    "display_name": "Insulin",
    "category": "METABOLIC",
    "panel_name": "Metabolic",
    "default_unit": "uIU/mL",
    "aliases": [
        "INSULIN",
        "Insulin",
    ],
},
"DHT": {
    "display_name": "DHT",
    "category": "HORMONE",
    "panel_name": "Hormone",
    "default_unit": None,
    "aliases": [
        "DHT",
    ],
},
"WHITE_BLOOD_CELL_COUNT": {
    "display_name": "White Blood Cell Count",
    "category": "CBC",
    "panel_name": "Complete Blood Count",
    "default_unit": "Thousand/uL",
    "aliases": [
        "WHITE BLOOD CELL COUNT",
        "WBC",
    ],
},
"SODIUM": {
    "display_name": "Sodium",
    "category": "CMP",
    "panel_name": "Comprehensive Metabolic Panel",
    "default_unit": "mmol/L",
    "aliases": ["SODIUM"],
},
"POTASSIUM": {
    "display_name": "Potassium",
    "category": "CMP",
    "panel_name": "Comprehensive Metabolic Panel",
    "default_unit": "mmol/L",
    "aliases": ["POTASSIUM"],
},
"CHLORIDE": {
    "display_name": "Chloride",
    "category": "CMP",
    "panel_name": "Comprehensive Metabolic Panel",
    "default_unit": "mmol/L",
    "aliases": ["CHLORIDE"],
},
"CARBON_DIOXIDE": {
    "display_name": "Carbon Dioxide",
    "category": "CMP",
    "panel_name": "Comprehensive Metabolic Panel",
    "default_unit": "mmol/L",
    "aliases": ["CARBON DIOXIDE", "CO2"],
},
"UREA_NITROGEN_BUN": {
    "display_name": "Urea Nitrogen (BUN)",
    "category": "CMP",
    "panel_name": "Comprehensive Metabolic Panel",
    "default_unit": "mg/dL",
    "aliases": ["UREA NITROGEN (BUN)", "BUN"],
},
"CREATININE": {
    "display_name": "Creatinine",
    "category": "CMP",
    "panel_name": "Comprehensive Metabolic Panel",
    "default_unit": "mg/dL",
    "aliases": ["CREATININE"],
},
"EGFR": {
    "display_name": "eGFR",
    "category": "CMP",
    "panel_name": "Comprehensive Metabolic Panel",
    "default_unit": None,
    "aliases": ["EGFR", "eGFR"],
},
"CALCIUM": {
    "display_name": "Calcium",
    "category": "CMP",
    "panel_name": "Comprehensive Metabolic Panel",
    "default_unit": "mg/dL",
    "aliases": ["CALCIUM"],
},
"PROTEIN_TOTAL": {
    "display_name": "Protein, Total",
    "category": "CMP",
    "panel_name": "Comprehensive Metabolic Panel",
    "default_unit": "g/dL",
    "aliases": ["PROTEIN, TOTAL"],
},
"ALBUMIN": {
    "display_name": "Albumin",
    "category": "CMP",
    "panel_name": "Comprehensive Metabolic Panel",
    "default_unit": "g/dL",
    "aliases": ["ALBUMIN"],
},
"GLOBULIN": {
    "display_name": "Globulin",
    "category": "CMP",
    "panel_name": "Comprehensive Metabolic Panel",
    "default_unit": "g/dL",
    "aliases": ["GLOBULIN"],
},
"ALBUMIN_GLOBULIN_RATIO": {
    "display_name": "Albumin/Globulin Ratio",
    "category": "CMP",
    "panel_name": "Comprehensive Metabolic Panel",
    "default_unit": None,
    "aliases": ["ALBUMIN/GLOBULIN RATIO"],
},
"BILIRUBIN_TOTAL": {
    "display_name": "Bilirubin, Total",
    "category": "CMP",
    "panel_name": "Comprehensive Metabolic Panel",
    "default_unit": "mg/dL",
    "aliases": ["BILIRUBIN, TOTAL"],
},
"ALKALINE_PHOSPHATASE": {
    "display_name": "Alkaline Phosphatase",
    "category": "CMP",
    "panel_name": "Comprehensive Metabolic Panel",
    "default_unit": "U/L",
    "aliases": ["ALKALINE PHOSPHATASE"],
},
"AST": {
    "display_name": "AST",
    "category": "CMP",
    "panel_name": "Comprehensive Metabolic Panel",
    "default_unit": "U/L",
    "aliases": ["AST"],
},
"ALT": {
    "display_name": "ALT",
    "category": "CMP",
    "panel_name": "Comprehensive Metabolic Panel",
    "default_unit": "U/L",
    "aliases": ["ALT"],
},
"URIC_ACID": {
    "display_name": "Uric Acid",
    "category": "METABOLIC",
    "panel_name": "Metabolic",
    "default_unit": "mg/dL",
    "aliases": ["URIC ACID"],
},

}

def upsert_catalog(session, canonical_code, config):
    row = session.query(LabTestCatalog).filter_by(canonical_code=canonical_code).first()
    if not row:
        row = LabTestCatalog(canonical_code=canonical_code)
        session.add(row)

    row.display_name = config["display_name"]
    row.category = config.get("category")
    row.panel_name = config.get("panel_name")
    row.default_unit = config.get("default_unit")
    row.active = 1


def upsert_alias(session, alias_name, canonical_code):
    row = session.query(LabTestAlias).filter_by(raw_name=alias_name).first()
    if not row:
        row = LabTestAlias(raw_name=alias_name)
        session.add(row)

    row.normalized_lookup = standardize_test_name(alias_name)
    row.canonical_code = canonical_code
    row.source_scope = "ANY"
    row.notes = None


def main():
    session = SessionLocal()
    try:
        for canonical_code, config in CANONICAL_TESTS.items():
            upsert_catalog(session, canonical_code, config)
            for alias_name in config["aliases"]:
                upsert_alias(session, alias_name, canonical_code)

        session.commit()
        print("Seeded lab test catalog and aliases successfully.")
    finally:
        session.close()


if __name__ == "__main__":
    main()