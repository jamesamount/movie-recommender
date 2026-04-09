from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT_DIR / "data"
RAW_TMDB_DIR = DATA_DIR / "raw" / "tmdb"
RAW_MOVIELENS_DIR = DATA_DIR / "raw" / "movielens"
DEMO_DIR = DATA_DIR / "demo"
PROCESSED_DIR = DATA_DIR / "processed"
MODELS_DIR = ROOT_DIR / "models" / "artifacts"

ARTIFACT_PATH = MODELS_DIR / "movie_recommender.joblib"
PROCESSED_CATALOG_PATH = PROCESSED_DIR / "catalog_preview.csv"
DEMO_CATALOG_PATH = DEMO_DIR / "demo_movies.csv"
LETTERBOXD_SAMPLE_PATH = DEMO_DIR / "sample_letterboxd_ratings.csv"

