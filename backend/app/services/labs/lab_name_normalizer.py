import re

def normalize_lab_name(source_name: str) -> str:
    """
    Returns a stable canonical name for common labs to normalize spreadsheet inputs safely.
    If no static mapping is known, returns a safe fallback derived directly from source_name.
    """
    if not source_name:
        return "unknown_test"
        
    s = source_name.lower().strip()
    
    # User-defined exact canonical mapping matrix 
    mappings = {
        "hemoglobin": "hemoglobin",
        "hgb": "hemoglobin",
        "hematocrit": "hematocrit",
        "hct": "hematocrit",
        "rbc": "rbc",
        "red blood cell": "rbc",
        "wbc": "wbc",
        "white blood cell": "wbc",
        "platelets": "platelets",
        "plt": "platelets",
        "glucose": "glucose",
        "a1c": "a1c",
        "hemoglobin a1c": "a1c",
        "hba1c": "a1c",
        "insulin": "insulin",
        "testosterone, total": "testosterone_total",
        "testosterone total": "testosterone_total",
        "testosterone, free": "testosterone_free",
        "testosterone free": "testosterone_free",
        "estradiol": "estradiol",
        "psa": "psa",
        "tsh": "tsh",
        "free t4": "free_t4",
        "t4, free": "free_t4",
        "free t3": "free_t3",
        "t3, free": "free_t3",
        "ast": "ast",
        "alt": "alt",
        "creatinine": "creatinine",
        "bun": "bun",
        "blood urea nitrogen": "bun",
        "egfr": "egfr",
        "cholesterol, total": "cholesterol_total",
        "cholesterol": "cholesterol_total",
        "ldl": "ldl",
        "hdl": "hdl",
        "triglycerides": "triglycerides",
    }
    
    # Exact matching override lookup
    if s in mappings:
        return mappings[s]
        
    # Substring matching fallback
    for key, canonical in mappings.items():
        if key in s:
            return canonical
            
    # Absolute safe fallback canonical generation logic replacing non-alphas
    safe_name = re.sub(r'[^a-z0-9]', '_', s)
    safe_name = re.sub(r'_+', '_', safe_name).strip('_')
    return safe_name
