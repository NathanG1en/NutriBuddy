import os
from dotenv import load_dotenv
from backend.config import settings

# Try loading explicitly
load_dotenv()

key_in_env = "GEMINI_API_KEY" in os.environ
key_val = os.environ.get("GEMINI_API_KEY", "")
print(f"GEMINI_API_KEY in os.environ: {key_in_env}")
print(f"Length of key in env: {len(key_val)}")

print(f"Settings gemini_api_key loaded: {bool(settings.gemini_api_key)}")
print(f"Settings gemini_api_key length: {len(settings.gemini_api_key)}")
