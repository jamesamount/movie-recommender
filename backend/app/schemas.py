from __future__ import annotations

from typing import Literal

from pydantic import BaseModel, Field


class MovieCard(BaseModel):
    movie_id: str
    title: str
    year: int | None = None
    genres: list[str] = Field(default_factory=list)
    director: str = ""
    rating: float = 0.0
    user_rating: float = 0.0
    popularity: float = 0.0
    runtime: int | None = None
    overview: str = ""
    poster_url: str = ""
    backdrop_url: str = ""
    source: str = ""
    quality_score: float = 0.0
    streaming_services: list[str] = Field(default_factory=list)
    watch_link: str = ""
    similarity: float | None = None
    hybrid_score: float | None = None


class SearchResponse(BaseModel):
    query: str
    results: list[MovieCard]


class SimilarResponse(BaseModel):
    seed_movie: MovieCard
    recommendations: list[MovieCard]
    method: Literal["cosine", "knn"]


class RandomResponse(BaseModel):
    movie: MovieCard


class RatedMovieInput(BaseModel):
    title: str
    year: int | None = None
    rating: float = 4.0


class PersonalizedRequest(BaseModel):
    favorite_titles: list[str] = Field(default_factory=list)
    rated_movies: list[RatedMovieInput] = Field(default_factory=list)
    top_n: int = 12
    genre: str | None = None
    decade: int | None = None
    min_rating: float | None = None
    runtime_max: int | None = None
    streaming_services: str | None = None


class PersonalizedResponse(BaseModel):
    seed_movies: list[MovieCard]
    recommendations: list[MovieCard]
    excluded_count: int


class LetterboxdImportResponse(BaseModel):
    imported_count: int
    imported_titles: list[str]
    message: str
    recommendations: list[MovieCard]
    seed_movies: list[MovieCard]
    excluded_count: int
    warnings: list[str] = Field(default_factory=list)


class HealthResponse(BaseModel):
    status: str
    dataset_source: str
    demo_mode: bool
    movie_count: int
    genres: list[str]
    decades: list[int]
    model_version: str
    streaming_filter_enabled: bool
    watch_region: str


class StreamingProvider(BaseModel):
    provider_id: int
    provider_name: str
    logo_path: str = ""


class StreamingProvidersResponse(BaseModel):
    enabled: bool
    watch_region: str
    providers: list[StreamingProvider]
    message: str = ""
