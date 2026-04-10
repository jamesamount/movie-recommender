from __future__ import annotations

from functools import lru_cache
from typing import Iterable

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics.pairwise import cosine_similarity

from ml.config import ARTIFACT_PATH
from ml.data_loader import resolve_title_matches


class RecommendationError(ValueError):
    """Raised when a recommendation request cannot be fulfilled."""


class MovieRecommenderEngine:
    def __init__(self, artifact: dict):
        self.artifact = artifact
        self.catalog: pd.DataFrame = artifact["catalog"].reset_index(drop=True)
        self.feature_matrix = artifact["feature_matrix"]
        self.nn_model = artifact.get("nn_model")
        self.dataset_source = artifact["dataset_source"]
        self.used_demo_data = self.catalog["source"].eq("demo_curated").all()

    @classmethod
    def from_path(cls, artifact_path=ARTIFACT_PATH) -> "MovieRecommenderEngine":
        artifact = joblib.load(artifact_path)
        return cls(artifact)

    @staticmethod
    def fix_tmdb_image_url(path, *, size: str) -> str:
        if path is None:
            return ""

        if pd.isna(path):
            return ""

        path = str(path).strip()
        if not path or path.lower() == "nan":
            return ""

        if path.startswith("http"):
            return path

        clean = path if path.startswith("/") else f"/{path}"
        return f"https://image.tmdb.org/t/p/{size}{clean}"

    def _base_record(self, row: pd.Series) -> dict:
        return {
            "movie_id": str(row["movie_id"]),
            "title": row["title"],
            "year": int(row["year"]) if row["year"] else None,
            "genres": row["genres"],
            "director": row["director"],
            "rating": round(float(row["vote_average"]), 2),
            "user_rating": round(float(row["avg_user_rating"]), 2),
            "popularity": round(float(row["popularity"]), 2),
            "runtime": int(row["runtime"]) if row["runtime"] else None,
            "overview": row["overview"],
            "poster_url": self.fix_tmdb_image_url(row.get("poster_url"), size="w500"),
            "backdrop_url": self.fix_tmdb_image_url(row.get("backdrop_url"), size="w780"),
            "source": row["source"],
            "quality_score": round(float(row["quality_score"]), 4),
        }

    def _top_ranked_indices(self, scores: np.ndarray, *, exclude_index: int | None, limit: int) -> np.ndarray:
        candidate_count = min(len(scores), max(limit * 4, limit + 24))
        if exclude_index is not None and candidate_count < len(scores):
            candidate_count += 1
        top_indices = np.argpartition(scores, -candidate_count)[-candidate_count:]
        ranked = top_indices[np.argsort(scores[top_indices])[::-1]]
        if exclude_index is not None:
            ranked = ranked[ranked != exclude_index]
        return ranked[:limit]

    def _passes_filters(
        self,
        row: pd.Series,
        *,
        genre: str | None = None,
        decade: int | None = None,
        min_rating: float | None = None,
        runtime_max: int | None = None,
    ) -> bool:
        if genre and genre.lower() not in {item.lower() for item in row["genres"]}:
            return False
        if decade is not None:
            if not row["year"] or int(row["year"]) // 10 * 10 != decade:
                return False
        if min_rating is not None and float(row["vote_average"]) < min_rating:
            return False
        if runtime_max is not None and row["runtime"] and float(row["runtime"]) > runtime_max:
            return False
        return True

    def _hybrid_score(self, similarity: float, quality_score: float) -> float:
        quality_component = min(max(quality_score / 10, 0.0), 1.0)
        return 0.78 * similarity + 0.22 * quality_component

    @staticmethod
    def _favorite_signature(favorite_titles: Iterable[str]) -> tuple[str, ...]:
        return tuple(str(title).strip() for title in favorite_titles if str(title).strip())

    @staticmethod
    def _rated_signature(rated_movies: Iterable[dict]) -> tuple[tuple[str, int | None, float], ...]:
        signature: list[tuple[str, int | None, float]] = []
        for entry in rated_movies:
            title = str(entry.get("title", "")).strip()
            if not title:
                continue
            year = entry.get("year")
            signature.append(
                (
                    title,
                    int(year) if year not in (None, "") else None,
                    round(float(entry.get("rating", 4.0)), 2),
                )
            )
        return tuple(signature)

    def get_movie_by_id(self, movie_id: str) -> tuple[int, pd.Series]:
        matches = self.catalog.index[self.catalog["movie_id"].astype(str) == str(movie_id)]
        if matches.empty:
            raise RecommendationError(f"Movie id '{movie_id}' was not found.")
        index = int(matches[0])
        return index, self.catalog.iloc[index]

    def get_movie_by_title(self, title: str) -> tuple[int, pd.Series]:
        matches = resolve_title_matches(self.catalog, [title])
        if not matches:
            partial = self.catalog[self.catalog["title"].str.contains(title, case=False, na=False)]
            if partial.empty:
                raise RecommendationError(f"Movie title '{title}' was not found.")
            return int(partial.index[0]), partial.iloc[0]
        index = matches[0]
        return index, self.catalog.iloc[index]

    def search(
        self,
        query: str,
        *,
        limit: int = 12,
        genre: str | None = None,
        decade: int | None = None,
        min_rating: float | None = None,
        runtime_max: int | None = None,
    ) -> list[dict]:
        if not query.strip():
            return []
        title_mask = self.catalog["title"].str.contains(query, case=False, na=False)
        director_mask = self.catalog["director"].str.contains(query, case=False, na=False)
        mask = title_mask | director_mask
        candidates = self.catalog[mask].copy()
        used_overview = False
        if candidates.empty and len(query.strip()) >= 4:
            overview_mask = self.catalog["overview"].str.contains(query, case=False, na=False)
            candidates = self.catalog[overview_mask].copy()
            used_overview = True
        if candidates.empty:
            return []
        candidates["query_score"] = (
            candidates["title"].str.contains(query, case=False, na=False).astype(int) * 2
            + candidates["director"].str.contains(query, case=False, na=False).astype(int)
            + (0 if used_overview else candidates["quality_score"] / 10)
        )
        candidates = candidates.sort_values(["query_score", "quality_score"], ascending=[False, False])
        results = []
        for _, row in candidates.iterrows():
            if self._passes_filters(
                row,
                genre=genre,
                decade=decade,
                min_rating=min_rating,
                runtime_max=runtime_max,
            ):
                results.append(self._base_record(row))
            if len(results) >= limit:
                break
        return results

    def catalog_candidates(
        self,
        *,
        genre: str | None = None,
        decade: int | None = None,
        min_rating: float | None = None,
        runtime_max: int | None = None,
        limit: int | None = None,
    ) -> list[dict]:
        candidates = self.catalog.sort_values(["quality_score", "popularity"], ascending=[False, False])
        records: list[dict] = []
        for _, row in candidates.iterrows():
            if self._passes_filters(
                row,
                genre=genre,
                decade=decade,
                min_rating=min_rating,
                runtime_max=runtime_max,
            ):
                records.append(self._base_record(row))
            if limit is not None and len(records) >= limit:
                break
        return records

    @lru_cache(maxsize=1024)
    def _similar_cached(
        self,
        movie_id: str,
        method: str,
        top_n: int,
        genre: str | None,
        decade: int | None,
        min_rating: float | None,
        runtime_max: int | None,
    ) -> tuple[dict, tuple[dict, ...]]:
        movie_index, anchor = self.get_movie_by_id(movie_id)
        if method == "knn":
            if self.nn_model is not None:
                distances, indices = self.nn_model.kneighbors(
                    self.feature_matrix[movie_index],
                    n_neighbors=min(top_n + 20, len(self.catalog)),
                )
                candidate_pairs = [
                    (int(index), float(1 - distance))
                    for distance, index in zip(distances[0], indices[0], strict=False)
                    if int(index) != movie_index
                ]
            else:
                scores = cosine_similarity(self.feature_matrix[movie_index], self.feature_matrix).ravel()
                ranked_indices = self._top_ranked_indices(scores, exclude_index=movie_index, limit=top_n + 24)
                candidate_pairs = [(int(index), float(scores[index])) for index in ranked_indices]
        else:
            scores = cosine_similarity(self.feature_matrix[movie_index], self.feature_matrix).ravel()
            ranked_indices = self._top_ranked_indices(scores, exclude_index=movie_index, limit=top_n + 24)
            candidate_pairs = [
                (int(index), float(scores[index]))
                for index in ranked_indices
            ]

        recommendations: list[dict] = []
        for candidate_index, similarity in candidate_pairs:
            row = self.catalog.iloc[candidate_index]
            if not self._passes_filters(
                row,
                genre=genre,
                decade=decade,
                min_rating=min_rating,
                runtime_max=runtime_max,
            ):
                continue
            payload = self._base_record(row)
            payload["similarity"] = round(similarity, 4)
            payload["hybrid_score"] = round(self._hybrid_score(similarity, float(row["quality_score"])), 4)
            recommendations.append(payload)
            if len(recommendations) >= top_n:
                break

        recommendations = sorted(recommendations, key=lambda item: item["hybrid_score"], reverse=True)
        return self._base_record(anchor), tuple(recommendations)

    def similar_movies(
        self,
        *,
        movie_id: str | None = None,
        title: str | None = None,
        method: str = "cosine",
        top_n: int = 10,
        genre: str | None = None,
        decade: int | None = None,
        min_rating: float | None = None,
        runtime_max: int | None = None,
    ) -> dict:
        if not movie_id and not title:
            raise RecommendationError("Provide either movie_id or title.")
        if not movie_id and title:
            movie_index, _ = self.get_movie_by_title(title)
            movie_id = str(self.catalog.iloc[movie_index]["movie_id"])
        seed, recommendations = self._similar_cached(
            str(movie_id),
            method,
            top_n,
            genre,
            decade,
            min_rating,
            runtime_max,
        )
        return {"seed_movie": seed, "recommendations": list(recommendations)}

    def random_movie(
        self,
        *,
        genre: str | None = None,
        decade: int | None = None,
        min_rating: float | None = None,
        runtime_max: int | None = None,
    ) -> dict:
        mask = self.catalog.apply(
            lambda row: self._passes_filters(
                row,
                genre=genre,
                decade=decade,
                min_rating=min_rating,
                runtime_max=runtime_max,
            ),
            axis=1,
        )
        candidates = self.catalog[mask]
        if candidates.empty:
            raise RecommendationError("No movies matched the selected filters.")

        weights = candidates["quality_score"].clip(lower=0.1)
        sampled = candidates.sample(n=1, weights=weights)
        return self._base_record(sampled.iloc[0])

    def personalized_recommendations(
        self,
        favorite_titles: Iterable[str] | None = None,
        rated_movies: Iterable[dict] | None = None,
        *,
        top_n: int = 12,
        genre: str | None = None,
        decade: int | None = None,
        min_rating: float | None = None,
        runtime_max: int | None = None,
    ) -> dict:
        favorite_titles = list(favorite_titles or [])
        rated_movies = list(rated_movies or [])
        seed_movies, recommendations, excluded_count = self._personalized_cached(
            self._favorite_signature(favorite_titles),
            self._rated_signature(rated_movies),
            top_n,
            genre,
            decade,
            min_rating,
            runtime_max,
        )
        return {
            "seed_movies": list(seed_movies),
            "recommendations": list(recommendations),
            "excluded_count": excluded_count,
        }

    @lru_cache(maxsize=256)
    def _personalized_cached(
        self,
        favorite_titles: tuple[str, ...],
        rated_movies: tuple[tuple[str, int | None, float], ...],
        top_n: int,
        genre: str | None,
        decade: int | None,
        min_rating: float | None,
        runtime_max: int | None,
    ) -> tuple[tuple[dict, ...], tuple[dict, ...], int]:
        rated_movie_payload = [
            {"title": title, "year": year, "rating": rating}
            for title, year, rating in rated_movies
        ]

        rated_titles = [entry["title"] for entry in rated_movie_payload if entry.get("title")]
        seed_indices = resolve_title_matches(self.catalog, list(favorite_titles) + rated_titles)
        if not seed_indices:
            raise RecommendationError("No favorite or rated movies matched the catalog.")

        watched_indices = set(seed_indices)
        weighted_rows = []
        for entry in rated_movie_payload:
            matches = resolve_title_matches(self.catalog, [entry.get("title", "")])
            if not matches:
                continue
            weight = float(entry.get("rating", 4.0))
            for index in matches:
                weighted_rows.append((index, max(weight, 0.5)))
        if not weighted_rows:
            weighted_rows = [(index, 5.0) for index in seed_indices]

        total_weight = sum(weight for _, weight in weighted_rows)
        profile = self.feature_matrix[weighted_rows[0][0]] * weighted_rows[0][1]
        for index, weight in weighted_rows[1:]:
            profile = profile + (self.feature_matrix[index] * weight)
        profile = profile / total_weight

        similarities = cosine_similarity(profile, self.feature_matrix).ravel()
        ranked_indices = self._top_ranked_indices(similarities, exclude_index=None, limit=top_n + len(watched_indices) + 24)

        recommendations = []
        for index in ranked_indices:
            if int(index) in watched_indices:
                continue
            row = self.catalog.iloc[int(index)]
            if not self._passes_filters(
                row,
                genre=genre,
                decade=decade,
                min_rating=min_rating,
                runtime_max=runtime_max,
            ):
                continue
            similarity = float(similarities[index])
            payload = self._base_record(row)
            payload["similarity"] = round(similarity, 4)
            payload["hybrid_score"] = round(self._hybrid_score(similarity, float(row["quality_score"])), 4)
            recommendations.append(payload)
            if len(recommendations) >= top_n:
                break

        seed_movies = [self._base_record(self.catalog.iloc[index]) for index in seed_indices[:8]]
        return tuple(seed_movies), tuple(recommendations), len(watched_indices)

    def list_filters(self) -> dict:
        genre_values = sorted({genre for genres in self.catalog["genres"] for genre in genres})
        decades = sorted({int(year) // 10 * 10 for year in self.catalog["year"] if int(year) > 0})
        return {
            "genres": genre_values,
            "decades": decades,
            "movie_count": int(len(self.catalog)),
            "dataset_source": self.dataset_source,
            "demo_mode": self.used_demo_data,
        }
