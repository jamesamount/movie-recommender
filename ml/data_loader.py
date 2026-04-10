from __future__ import annotations

import ast
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

import numpy as np
import pandas as pd

from ml.config import (
    BUILD_PROFILE,
    DEMO_CATALOG_PATH,
    DEPLOY_CATALOG_LIMIT,
    DEPLOY_MIN_VOTE_COUNT,
    RAW_MOVIELENS_DIR,
    RAW_TMDB_DIR,
)


@dataclass(slots=True)
class DatasetLoadResult:
    catalog: pd.DataFrame
    source_name: str
    used_demo_data: bool


def _safe_literal_eval(value: object) -> list[dict]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return []
    if isinstance(value, list):
        return value
    if not isinstance(value, str) or not value.strip():
        return []
    try:
        parsed = ast.literal_eval(value)
    except (ValueError, SyntaxError):
        return []
    return parsed if isinstance(parsed, list) else []


def _extract_names(value: object, *, limit: int | None = None) -> list[str]:
    items = _safe_literal_eval(value)
    names = [str(item.get("name", "")).strip() for item in items if item.get("name")]
    if limit is not None:
        names = names[:limit]
    return [name for name in names if name]


def _extract_director(value: object) -> str:
    items = _safe_literal_eval(value)
    for item in items:
        if item.get("job") == "Director" and item.get("name"):
            return str(item["name"]).strip()
    return ""


def _split_pipe_list(value: object) -> list[str]:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return []
    if isinstance(value, list):
        return [str(part).strip() for part in value if str(part).strip()]
    text = str(value).strip()
    if not text:
        return []
    return [part.strip() for part in text.split("|") if part.strip()]


def _normalize_title(value: object) -> str:
    return "".join(char.lower() for char in str(value) if char.isalnum() or char.isspace()).strip()


def _coerce_float(series: pd.Series, default: float = 0.0) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(default).astype(float)


def _coerce_int(series: pd.Series, default: int = 0) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").fillna(default).astype(int)


def _ensure_demo_catalog() -> pd.DataFrame:
    if not DEMO_CATALOG_PATH.exists():
        raise FileNotFoundError(
            f"Demo dataset not found at {DEMO_CATALOG_PATH}. "
            "The project expects either demo_movies.csv or real raw datasets."
        )

    catalog = pd.read_csv(DEMO_CATALOG_PATH)
    catalog["genres"] = catalog["genres"].map(_split_pipe_list)
    catalog["keywords"] = catalog["keywords"].map(_split_pipe_list)
    catalog["cast"] = catalog["cast"].map(_split_pipe_list)
    catalog["director"] = catalog["director"].fillna("").astype(str)
    catalog["overview"] = catalog["overview"].fillna("").astype(str)
    catalog["year"] = _coerce_int(catalog["year"])
    catalog["vote_average"] = _coerce_float(catalog["vote_average"])
    catalog["vote_count"] = _coerce_int(catalog["vote_count"])
    catalog["popularity"] = _coerce_float(catalog["popularity"])
    catalog["runtime"] = _coerce_float(catalog["runtime"])
    catalog["avg_user_rating"] = _coerce_float(catalog["avg_user_rating"])
    catalog["user_rating_count"] = _coerce_int(catalog["user_rating_count"])
    catalog["movie_id"] = catalog["movie_id"].astype(str)
    catalog["poster_url"] = catalog["poster_url"].fillna("").astype(str)
    if "backdrop_url" not in catalog.columns:
        catalog["backdrop_url"] = ""
    catalog["backdrop_url"] = catalog["backdrop_url"].fillna("").astype(str)
    catalog["source"] = catalog["source"].fillna("demo_curated").astype(str)
    return catalog


def _tmdb_files_available() -> bool:
    required = [
        RAW_TMDB_DIR / "movies_metadata.csv",
        RAW_TMDB_DIR / "credits.csv",
        RAW_TMDB_DIR / "keywords.csv",
    ]
    return all(path.exists() for path in required)


def _load_movielens_rating_stats() -> pd.DataFrame:
    ratings_path = RAW_MOVIELENS_DIR / "ratings.csv"
    links_path = RAW_MOVIELENS_DIR / "links.csv"

    if ratings_path.exists() and links_path.exists():
        ratings = pd.read_csv(ratings_path, usecols=["movieId", "rating"])
        links = pd.read_csv(links_path, usecols=["movieId", "tmdbId"])
    else:
        ratings_path = RAW_TMDB_DIR / "ratings_small.csv"
        links_path = RAW_TMDB_DIR / "links_small.csv"
        if not ratings_path.exists() or not links_path.exists():
            return pd.DataFrame(columns=["tmdb_id", "avg_user_rating", "user_rating_count"])
        ratings = pd.read_csv(ratings_path, usecols=["movieId", "rating"])
        links = pd.read_csv(links_path, usecols=["movieId", "tmdbId"])

    links["tmdbId"] = pd.to_numeric(links["tmdbId"], errors="coerce")
    merged = ratings.merge(links.dropna(subset=["tmdbId"]), on="movieId", how="inner")
    grouped = (
        merged.groupby("tmdbId")["rating"]
        .agg(avg_user_rating="mean", user_rating_count="count")
        .reset_index()
        .rename(columns={"tmdbId": "tmdb_id"})
    )
    grouped["tmdb_id"] = grouped["tmdb_id"].astype(int)
    return grouped


def _build_tmdb_catalog() -> pd.DataFrame:
    movie_columns = pd.read_csv(RAW_TMDB_DIR / "movies_metadata.csv", nrows=0).columns.tolist()
    selected_movie_columns = [
        column
        for column in [
            "id",
            "title",
            "overview",
            "genres",
            "release_date",
            "vote_average",
            "vote_count",
            "popularity",
            "runtime",
            "poster_path",
            "backdrop_path",
        ]
        if column in movie_columns
    ]
    movies = pd.read_csv(
        RAW_TMDB_DIR / "movies_metadata.csv",
        low_memory=False,
        usecols=selected_movie_columns,
    )
    credits = pd.read_csv(RAW_TMDB_DIR / "credits.csv", usecols=["id", "cast", "crew"])
    keywords = pd.read_csv(RAW_TMDB_DIR / "keywords.csv", usecols=["id", "keywords"])

    movies["id"] = pd.to_numeric(movies["id"], errors="coerce")
    credits["id"] = pd.to_numeric(credits["id"], errors="coerce")
    keywords["id"] = pd.to_numeric(keywords["id"], errors="coerce")

    movies = movies.dropna(subset=["id", "title"]).copy()
    movies["tmdb_id"] = movies["id"].astype(int)
    credits = credits.dropna(subset=["id"]).copy()
    credits["tmdb_id"] = credits["id"].astype(int)
    keywords = keywords.dropna(subset=["id"]).copy()
    keywords["tmdb_id"] = keywords["id"].astype(int)

    merged = (
        movies.merge(credits[["tmdb_id", "cast", "crew"]], on="tmdb_id", how="left")
        .merge(keywords[["tmdb_id", "keywords"]], on="tmdb_id", how="left")
    )

    rating_stats = _load_movielens_rating_stats()
    merged = merged.merge(rating_stats, on="tmdb_id", how="left")

    merged["year"] = pd.to_datetime(merged["release_date"], errors="coerce").dt.year.fillna(0).astype(int)
    merged["genres"] = merged["genres"].map(_extract_names)
    merged["keywords"] = merged["keywords"].map(lambda value: _extract_names(value, limit=12))
    merged["cast"] = merged["cast"].map(lambda value: _extract_names(value, limit=6))
    merged["director"] = merged["crew"].map(_extract_director)
    merged["overview"] = merged["overview"].fillna("").astype(str)
    merged["vote_average"] = _coerce_float(merged["vote_average"])
    merged["vote_count"] = _coerce_int(merged["vote_count"])
    merged["popularity"] = _coerce_float(merged["popularity"])
    merged["runtime"] = _coerce_float(merged["runtime"])
    merged["avg_user_rating"] = _coerce_float(merged["avg_user_rating"], default=np.nan).fillna(
        merged["vote_average"] / 2
    )
    merged["user_rating_count"] = _coerce_int(merged["user_rating_count"])
    merged["poster_url"] = merged["poster_path"].fillna("").map(
        lambda path: f"https://image.tmdb.org/t/p/w342{path}" if path else ""
    )
    merged["backdrop_path"] = merged.get("backdrop_path", "").fillna("") if "backdrop_path" in merged else ""
    merged["backdrop_url"] = pd.Series(merged["backdrop_path"]).fillna("").map(
        lambda path: f"https://image.tmdb.org/t/p/w780{path}" if path else ""
    )
    merged["source"] = "tmdb_movielens"
    merged["movie_id"] = merged["tmdb_id"].astype(str)

    merged["normalized_title"] = merged["title"].map(_normalize_title)
    merged = merged.sort_values(["vote_count", "popularity"], ascending=[False, False])
    merged = merged.drop_duplicates(subset=["normalized_title", "year"], keep="first")

    columns = [
        "movie_id",
        "tmdb_id",
        "title",
        "year",
        "genres",
        "keywords",
        "cast",
        "director",
        "overview",
        "vote_average",
        "vote_count",
        "popularity",
        "runtime",
        "avg_user_rating",
        "user_rating_count",
        "poster_url",
        "backdrop_url",
        "source",
    ]
    catalog = merged[columns].reset_index(drop=True)

    if BUILD_PROFILE == "deploy":
        catalog = catalog[
            (catalog["vote_count"] >= DEPLOY_MIN_VOTE_COUNT)
            | (catalog["popularity"] >= catalog["popularity"].quantile(0.60))
        ].copy()
        catalog = catalog.sort_values(
            ["vote_count", "popularity", "vote_average"],
            ascending=[False, False, False],
        ).head(DEPLOY_CATALOG_LIMIT)

    return catalog.reset_index(drop=True)


def load_movie_catalog() -> DatasetLoadResult:
    if _tmdb_files_available():
        catalog = _build_tmdb_catalog()
        if not catalog.empty:
            return DatasetLoadResult(
                catalog=catalog,
                source_name="TMDb metadata merged with MovieLens ratings",
                used_demo_data=False,
            )

    demo_catalog = _ensure_demo_catalog()
    return DatasetLoadResult(
        catalog=demo_catalog,
        source_name="Curated demo subset of real movies for offline development",
        used_demo_data=True,
    )


def build_title_index(catalog: pd.DataFrame) -> dict[str, list[int]]:
    title_map: dict[str, list[int]] = {}
    for index, row in catalog.iterrows():
        keys = {
            _normalize_title(row["title"]),
            _normalize_title(f"{row['title']} {row['year']}"),
        }
        for key in keys:
            if key:
                title_map.setdefault(key, []).append(index)
    return title_map


def resolve_title_matches(catalog: pd.DataFrame, titles: Iterable[str]) -> list[int]:
    title_index = build_title_index(catalog)
    matches: list[int] = []
    for title in titles:
        normalized = _normalize_title(title)
        for index in title_index.get(normalized, []):
            matches.append(index)
    return list(dict.fromkeys(matches))
