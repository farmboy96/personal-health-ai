import os
from pydantic_settings import BaseSettings, SettingsConfigDict

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    PROJECT_NAME: str = "Personal Health AI"
    # The API Key for the official google-genai SDK
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    # Path configuration
    BASE_DIR: str = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    DATA_DIR: str = os.path.join(BASE_DIR, "data")
    RAW_DATA_DIR: str = os.path.join(DATA_DIR, "raw")
    
    # Configure the raw_payload storage policy: 'none', 'selected_metrics', 'all'
    PAYLOAD_STORAGE_POLICY: str = "selected_metrics"

settings = Settings()

# Ensure directories exist
os.makedirs(settings.RAW_DATA_DIR, exist_ok=True)
