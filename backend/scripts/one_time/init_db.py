from app.db.database import engine, Base
from app.db.models import * # Ensure models are loaded to create tables
from app.core.config import settings
import os

def init():
    print(f"Creating raw directories at {settings.RAW_DATA_DIR}")
    os.makedirs(settings.RAW_DATA_DIR, exist_ok=True)
    
    print("Creating SQLite schema in database...")
    Base.metadata.create_all(bind=engine)
    print("Database initialization complete.")

if __name__ == "__main__":
    init()
