import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()

ROOT_DIR = Path(__file__).resolve().parents[2]
FRONTEND_DIR = ROOT_DIR / "frontend"

TMDB_API_BASE_URL = os.getenv("TMDB_API_BASE_URL", "https://api.themoviedb.org/3")
TMDB_API_KEY = os.getenv("TMDB_API_KEY", "")
TMDB_API_READ_ACCESS_TOKEN = os.getenv("TMDB_API_READ_ACCESS_TOKEN", "")
TMDB_WATCH_REGION = os.getenv("TMDB_WATCH_REGION", "US").upper()
TMDB_REQUEST_TIMEOUT_SECONDS = float(os.getenv("TMDB_REQUEST_TIMEOUT_SECONDS", "4.5"))
