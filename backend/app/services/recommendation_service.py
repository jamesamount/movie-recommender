from __future__ import annotations

from functools import lru_cache

from ml.build_pipeline import main as build_pipeline
from ml.config import ARTIFACT_PATH
from ml.recommender import MovieRecommenderEngine


@lru_cache(maxsize=1)
def get_recommendation_engine() -> MovieRecommenderEngine:
    if not ARTIFACT_PATH.exists():
        build_pipeline()
    return MovieRecommenderEngine.from_path(ARTIFACT_PATH)

