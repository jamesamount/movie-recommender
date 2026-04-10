import os
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = Path(os.getenv("MOVIE_DATA_DIR", ROOT_DIR / "data"))
RAW_TMDB_DIR = Path(os.getenv("MOVIE_RAW_TMDB_DIR", DATA_DIR / "raw" / "tmdb"))
RAW_MOVIELENS_DIR = Path(os.getenv("MOVIE_RAW_MOVIELENS_DIR", DATA_DIR / "raw" / "movielens"))
DEMO_DIR = Path(os.getenv("MOVIE_DEMO_DIR", DATA_DIR / "demo"))
PROCESSED_DIR = Path(os.getenv("MOVIE_PROCESSED_DIR", DATA_DIR / "processed"))
MODELS_DIR = Path(os.getenv("MOVIE_MODELS_DIR", ROOT_DIR / "models" / "artifacts"))

ARTIFACT_PATH = Path(os.getenv("MOVIE_ARTIFACT_PATH", MODELS_DIR / "movie_recommender.joblib"))
PROCESSED_CATALOG_PATH = Path(
    os.getenv("MOVIE_PROCESSED_CATALOG_PATH", PROCESSED_DIR / "catalog_preview.csv")
)
DEMO_CATALOG_PATH = Path(os.getenv("MOVIE_DEMO_CATALOG_PATH", DEMO_DIR / "demo_movies.csv"))
LETTERBOXD_SAMPLE_PATH = Path(
    os.getenv("MOVIE_LETTERBOXD_SAMPLE_PATH", DEMO_DIR / "sample_letterboxd_ratings.csv")
)

BUILD_PROFILE = os.getenv("MOVIE_BUILD_PROFILE", "full").strip().lower()
DEPLOY_CATALOG_LIMIT = int(os.getenv("MOVIE_DEPLOY_CATALOG_LIMIT", "12000"))
DEPLOY_MIN_VOTE_COUNT = int(os.getenv("MOVIE_DEPLOY_MIN_VOTE_COUNT", "40"))
TFIDF_MAX_FEATURES = int(
    os.getenv(
        "MOVIE_TFIDF_MAX_FEATURES",
        "7000" if BUILD_PROFILE == "deploy" else "15000",
    )
)
TEXT_NGRAM_MAX = int(
    os.getenv(
        "MOVIE_TFIDF_NGRAM_MAX",
        "1" if BUILD_PROFILE == "deploy" else "2",
    )
)
STORE_NN_MODEL = os.getenv(
    "MOVIE_STORE_NN_MODEL",
    "0" if BUILD_PROFILE == "deploy" else "1",
).strip() not in {"0", "false", "False"}
