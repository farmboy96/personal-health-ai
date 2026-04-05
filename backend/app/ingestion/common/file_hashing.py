import hashlib

def calculate_file_hash(filepath: str) -> str:
    hasher = hashlib.sha256()
    with open(filepath, 'rb') as f:
        for chunk in iter(lambda: f.read(4096), b""):
            hasher.update(chunk)
    return hasher.hexdigest()

def generate_lab_dedupe_hash(source_file_name: str, lab_date: str, source_test_name: str, value_str: str, unit: str) -> str:
    """
    Builds a deterministic dedupe hash from exact source data strings to securely block duplicates.
    """
    components = [
        str(source_file_name).strip() if source_file_name else "",
        str(lab_date).strip() if lab_date else "",
        str(source_test_name).strip().lower() if source_test_name else "",
        str(value_str).strip() if value_str else "",
        str(unit).strip().lower() if unit else ""
    ]
    raw_hash_string = "|".join(components)
    return hashlib.sha256(raw_hash_string.encode('utf-8')).hexdigest()
