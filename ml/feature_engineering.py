from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone

import joblib
import numpy as np
import pandas as pd
from scipy import sparse
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.neighbors import NearestNeighbors
from sklearn.preprocessing import MinMaxScaler, StandardScaler, normalize

from ml.config import ARTIFACT_PATH, MODELS_DIR, PROCESSED_CATALOG_PATH, PROCESSED_DIR


NUMERIC_COLUMNS = [
    "year",
    "vote_average",
    "vote_count",
    "popularity",
    "runtime",
    "avg_user_rating",
    "user_rating_count",
]


@dataclass(slots=True)
class ArtifactBuildResult:
    artifact: dict
    catalog_preview: pd.DataFrame


def _build_text_blob(row: pd.Series) -> str:
    decade = f"{int(row['year']) // 10 * 10}s" if row["year"] else "unknown decade"
    tokens = [
        row["title"],
        row["overview"],
        " ".join(row["genres"]),
        " ".join(row["keywords"]),
        " ".join(row["cast"]),
        row["director"],
        decade,
    ]
    return " ".join(str(token).strip() for token in tokens if str(token).strip())


def _build_quality_score(catalog: pd.DataFrame) -> pd.Series:
    vote_count = catalog["vote_count"].fillna(0)
    vote_average = catalog["vote_average"].fillna(0)
    popularity = catalog["popularity"].fillna(0)

    minimum_votes = vote_count.quantile(0.60) if len(vote_count) else 0
    global_mean = vote_average.mean() if len(vote_average) else 0

    weighted_rating = (
        (vote_count / (vote_count + minimum_votes)).replace([np.inf, -np.inf], 0).fillna(0) * vote_average
        + (minimum_votes / (vote_count + minimum_votes)).replace([np.inf, -np.inf], 0).fillna(0) * global_mean
    )
    if len(popularity):
        popularity_norm = MinMaxScaler().fit_transform(popularity.to_frame()).ravel()
    else:
        popularity_norm = np.zeros(len(catalog))

    quality = 0.7 * weighted_rating + 0.3 * popularity_norm * 10
    return pd.Series(quality, index=catalog.index)


def build_artifact(catalog: pd.DataFrame, dataset_source: str) -> ArtifactBuildResult:
    working = catalog.copy()
    for column in ["genres", "keywords", "cast"]:
        working[column] = working[column].apply(lambda value: value if isinstance(value, list) else [])

    working["text_blob"] = working.apply(_build_text_blob, axis=1)
    working["quality_score"] = _build_quality_score(working)
    working["genre_tokens"] = working["genres"].apply(lambda values: ", ".join(values))

    vectorizer = TfidfVectorizer(
        stop_words="english",
        ngram_range=(1, 2),
        max_features=15000,
        min_df=1,
    )
    text_matrix = vectorizer.fit_transform(working["text_blob"])

    numeric_frame = working[NUMERIC_COLUMNS].apply(pd.to_numeric, errors="coerce").fillna(0.0)
    scaler = StandardScaler(with_mean=False)
    numeric_matrix = sparse.csr_matrix(scaler.fit_transform(numeric_frame))

    feature_matrix = normalize(sparse.hstack([text_matrix, numeric_matrix]).tocsr())

    nn_model = NearestNeighbors(metric="cosine", algorithm="brute", n_neighbors=min(50, len(working)))
    nn_model.fit(feature_matrix)

    artifact = {
        "catalog": working,
        "feature_matrix": feature_matrix,
        "vectorizer": vectorizer,
        "numeric_scaler": scaler,
        "nn_model": nn_model,
        "dataset_source": dataset_source,
        "built_at_utc": datetime.now(timezone.utc).isoformat(),
        "model_version": "1.0.0",
        "numeric_columns": NUMERIC_COLUMNS,
    }

    preview = working[
        [
            "movie_id",
            "title",
            "year",
            "genre_tokens",
            "vote_average",
            "avg_user_rating",
            "quality_score",
            "source",
        ]
    ].rename(columns={"genre_tokens": "genres"})
    return ArtifactBuildResult(artifact=artifact, catalog_preview=preview)


def save_artifact(result: ArtifactBuildResult) -> None:
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    PROCESSED_DIR.mkdir(parents=True, exist_ok=True)
    joblib.dump(result.artifact, ARTIFACT_PATH)
    result.catalog_preview.to_csv(PROCESSED_CATALOG_PATH, index=False)

