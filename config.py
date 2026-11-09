import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

# Required
IMMICH_URL = os.getenv("IMMICH_URL", "").rstrip("/")
IMMICH_API_KEY = os.getenv("IMMICH_API_KEY", "")

# Optional
MEDAL_PATH = os.getenv("MEDAL_PATH", r"D:\Medal")
ALBUM_NAME = os.getenv("ALBUM_NAME", "Medal")
DASHBOARD_PORT = int(os.getenv("DASHBOARD_PORT", "8765"))
FALLBACK_URL = os.getenv("FALLBACK_URL", "").rstrip("/")

# Derived
MEDAL_DIR = Path(MEDAL_PATH)


def validate():
    """Validate required configuration and return list of errors."""
    errors = []
    if not IMMICH_URL:
        errors.append("IMMICH_URL is not set. Set it in .env or as an environment variable.")
    if not IMMICH_API_KEY:
        errors.append("IMMICH_API_KEY is not set. Set it in .env or as an environment variable.")
    if not MEDAL_DIR.exists():
        errors.append(f"MEDAL_PATH '{MEDAL_PATH}' does not exist.")
    return errors
