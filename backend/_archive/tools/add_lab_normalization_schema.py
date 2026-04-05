import sqlite3

DB_PATH = r"C:\health_ai_data\db\health.db"

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

columns_to_add = [
    ("canonical_test_code", "TEXT"),
    ("canonical_test_name", "TEXT"),
    ("test_category", "TEXT"),
    ("panel_name", "TEXT"),
]

for col_name, col_type in columns_to_add:
    try:
        cur.execute(f"ALTER TABLE lab_results ADD COLUMN {col_name} {col_type}")
        print(f"Added column: {col_name}")
    except sqlite3.OperationalError as e:
        if "duplicate column name" in str(e).lower():
            print(f"Column already exists: {col_name}")
        else:
            raise

cur.execute("""
CREATE TABLE IF NOT EXISTS lab_test_catalog (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_code TEXT NOT NULL UNIQUE,
    display_name TEXT NOT NULL,
    category TEXT,
    panel_name TEXT,
    default_unit TEXT,
    active INTEGER NOT NULL DEFAULT 1
)
""")

cur.execute("""
CREATE TABLE IF NOT EXISTS lab_test_alias (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    raw_name TEXT NOT NULL UNIQUE,
    normalized_lookup TEXT NOT NULL,
    canonical_code TEXT NOT NULL,
    source_scope TEXT,
    notes TEXT
)
""")

cur.execute("""
CREATE INDEX IF NOT EXISTS idx_lab_test_alias_lookup
ON lab_test_alias(normalized_lookup)
""")

cur.execute("""
CREATE INDEX IF NOT EXISTS idx_lab_test_alias_code
ON lab_test_alias(canonical_code)
""")

conn.commit()
conn.close()

print("Schema update complete.")