import os
from pathlib import Path

from dotenv import load_dotenv
from openai import OpenAI

load_dotenv(Path(__file__).resolve().parents[2] / ".env")

def get_openai_client():
    return OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
