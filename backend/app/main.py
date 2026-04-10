from __future__ import annotations

import random
from pathlib import Path

from fastapi import FastAPI, File, Form, HTTPException, Query, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from backend.app.config import FRONTEND_DIR
from backend.app.schemas import (
    HealthResponse,
    LetterboxdImportResponse,
    PersonalizedRequest,
    PersonalizedResponse,
    RandomResponse,
    SearchResponse,
    SimilarResponse,
    StreamingProvidersResponse,
)
from backend.app.services.letterboxd import LetterboxdImportError, LetterboxdImporter
from backend.app.services.recommendation_service import (
    get_recommendation_engine,
    get_streaming_provider_service,
)
from backend.app.services.streaming_providers import StreamingProviderError
from ml.recommender import RecommendationError

app = FastAPI(
    title="CineMatch ML",
    description="A portfolio-ready movie recommendation engine using content features, cosine similarity, and k-NN retrieval.",
    version="1.0.0",
)


def _parse_streaming_services(raw_value: str | None) -> list[str]:
    if not raw_value or not isinstance(raw_value, str):
        return []
    return [item.strip() for item in raw_value.split(",") if item.strip()]


def _apply_streaming_filter(
    movies: list[dict],
    *,
    selected_services: list[str],
    expand_pool_message: str | None = None,
) -> list[dict]:
    streaming_service = get_streaming_provider_service()
    if not selected_services:
        return movies
    try:
        filtered = streaming_service.filter_movies(movies, selected_services)
    except StreamingProviderError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    if not filtered and expand_pool_message:
        raise HTTPException(status_code=404, detail=expand_pool_message)
    return filtered


def _enrich_media(movies: list[dict]) -> list[dict]:
    streaming_service = get_streaming_provider_service()
    if not streaming_service.enabled:
        return movies
    return streaming_service.enrich_movies_media(movies)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

if FRONTEND_DIR.exists():
    app.mount("/frontend", StaticFiles(directory=FRONTEND_DIR), name="frontend")


@app.get("/", include_in_schema=False)
def frontend_index() -> FileResponse:
    index_path = FRONTEND_DIR / "index.html"
    if not index_path.exists():
        raise HTTPException(status_code=404, detail="Frontend assets were not found.")
    return FileResponse(index_path)


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    engine = get_recommendation_engine()
    filters = engine.list_filters()
    streaming_service = get_streaming_provider_service()
    return HealthResponse(
        status="ok",
        dataset_source=filters["dataset_source"],
        demo_mode=filters["demo_mode"],
        movie_count=filters["movie_count"],
        genres=filters["genres"],
        decades=filters["decades"],
        model_version=engine.artifact["model_version"],
        streaming_filter_enabled=streaming_service.enabled,
        watch_region=streaming_service.watch_region,
    )


@app.get("/streaming/providers", response_model=StreamingProvidersResponse)
def streaming_providers() -> StreamingProvidersResponse:
    streaming_service = get_streaming_provider_service()
    providers = streaming_service.list_providers()
    return StreamingProvidersResponse(
        enabled=streaming_service.enabled,
        watch_region=streaming_service.watch_region,
        providers=providers,
        message=streaming_service.provider_message(),
    )


@app.get("/search", response_model=SearchResponse)
def search_movies(
    q: str = Query(..., min_length=1),
    limit: int = Query(12, ge=1, le=30),
    genre: str | None = Query(None),
    decade: int | None = Query(None),
    min_rating: float | None = Query(None, ge=0, le=10),
    runtime_max: int | None = Query(None, ge=1),
    streaming_services: str | None = Query(None),
) -> SearchResponse:
    engine = get_recommendation_engine()
    requested_services = _parse_streaming_services(streaming_services)
    results = engine.search(
        q,
        limit=max(limit * 4, limit),
        genre=genre,
        decade=decade,
        min_rating=min_rating,
        runtime_max=runtime_max,
    )
    results = _apply_streaming_filter(
        results,
        selected_services=requested_services,
        expand_pool_message="No search results matched the selected streaming services.",
    )[:limit]
    return SearchResponse(query=q, results=results)


@app.get("/recommend/similar", response_model=SimilarResponse)
def recommend_similar(
    movie_id: str | None = Query(None),
    title: str | None = Query(None),
    method: str = Query("cosine", pattern="^(cosine|knn)$"),
    top_n: int = Query(10, ge=1, le=30),
    genre: str | None = Query(None),
    decade: int | None = Query(None),
    min_rating: float | None = Query(None, ge=0, le=10),
    runtime_max: int | None = Query(None, ge=1),
    streaming_services: str | None = Query(None),
) -> SimilarResponse:
    engine = get_recommendation_engine()
    requested_services = _parse_streaming_services(streaming_services)
    try:
        payload = engine.similar_movies(
            movie_id=movie_id,
            title=title,
            method=method,
            top_n=max(top_n * 4, top_n),
            genre=genre,
            decade=decade,
            min_rating=min_rating,
            runtime_max=runtime_max,
        )
    except RecommendationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    payload["recommendations"] = _apply_streaming_filter(
        payload["recommendations"],
        selected_services=requested_services,
        expand_pool_message="No similar movies matched the selected streaming services.",
    )[:top_n]
    payload["seed_movie"] = _enrich_media([payload["seed_movie"]])[0]
    payload["recommendations"] = _enrich_media(payload["recommendations"])
    return SimilarResponse(method=method, **payload)


@app.get("/recommend/random", response_model=RandomResponse)
def recommend_random(
    genre: str | None = Query(None),
    decade: int | None = Query(None),
    min_rating: float | None = Query(None, ge=0, le=10),
    runtime_max: int | None = Query(None, ge=1),
    streaming_services: str | None = Query(None),
) -> RandomResponse:
    engine = get_recommendation_engine()
    requested_services = _parse_streaming_services(streaming_services)
    try:
        if requested_services:
            candidate_titles = engine.catalog_candidates(
                genre=genre,
                decade=decade,
                min_rating=min_rating,
                runtime_max=runtime_max,
                limit=max(len(engine.catalog), 250),
            )
            filtered = _apply_streaming_filter(
                candidate_titles,
                selected_services=requested_services,
                expand_pool_message="No random candidates matched the selected streaming services.",
            )
            if not filtered:
                raise RecommendationError("No random candidates matched the selected streaming services.")
            movie = random.choice(filtered)
        else:
            movie = engine.random_movie(
                genre=genre,
                decade=decade,
                min_rating=min_rating,
                runtime_max=runtime_max,
            )
    except RecommendationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    movie = _enrich_media([movie])[0]
    return RandomResponse(movie=movie)


@app.post("/recommend/personalized", response_model=PersonalizedResponse)
def recommend_personalized(payload: PersonalizedRequest) -> PersonalizedResponse:
    engine = get_recommendation_engine()
    try:
        result = engine.personalized_recommendations(
            favorite_titles=payload.favorite_titles,
            rated_movies=[entry.model_dump() for entry in payload.rated_movies],
            top_n=max(payload.top_n * 4, payload.top_n),
            genre=payload.genre,
            decade=payload.decade,
            min_rating=payload.min_rating,
            runtime_max=payload.runtime_max,
        )
    except RecommendationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    selected_services = _parse_streaming_services(getattr(payload, "streaming_services", None))
    result["recommendations"] = _apply_streaming_filter(
        result["recommendations"],
        selected_services=selected_services,
        expand_pool_message="No personalized recommendations matched the selected streaming services.",
    )[: payload.top_n]
    result["seed_movies"] = _enrich_media(result["seed_movies"])
    result["recommendations"] = _enrich_media(result["recommendations"])
    return PersonalizedResponse(**result)


@app.post("/letterboxd/import", response_model=LetterboxdImportResponse)
async def import_letterboxd(
    file: UploadFile | None = File(None),
    csv_text: str | None = Form(None),
    username: str | None = Form(None),
    top_n: int = Form(12),
    genre: str | None = Form(None),
    decade: int | None = Form(None),
    min_rating: float | None = Form(None),
    runtime_max: int | None = Form(None),
    streaming_services: str | None = Form(None),
) -> LetterboxdImportResponse:
    engine = get_recommendation_engine()
    importer = LetterboxdImporter()
    warnings: list[str] = []

    try:
        if file is not None:
            frame = importer.parse_csv_bytes(await file.read())
            message = f"Imported {len(frame)} movies from {file.filename or 'Letterboxd CSV'}."
        elif csv_text:
            frame = importer.parse_csv_text(csv_text)
            message = f"Imported {len(frame)} movies from pasted Letterboxd CSV data."
        elif username:
            frame = importer.scrape_public_username(username)
            message = f"Imported {len(frame)} movies from public Letterboxd profile {username}."
            warnings.append("Username scraping is best-effort only. CSV export import is the preferred path.")
        else:
            raise LetterboxdImportError("Upload a Letterboxd CSV, paste CSV text, or provide a public username.")

        favorite_titles, rated_movies = importer.to_personalization_payload(frame)
        result = engine.personalized_recommendations(
            favorite_titles=favorite_titles,
            rated_movies=rated_movies,
            top_n=max(top_n * 4, top_n),
            genre=genre,
            decade=decade,
            min_rating=min_rating,
            runtime_max=runtime_max,
        )
    except LetterboxdImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RecommendationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    selected_services = _parse_streaming_services(streaming_services)
    result["recommendations"] = _apply_streaming_filter(
        result["recommendations"],
        selected_services=selected_services,
        expand_pool_message="No Letterboxd recommendations matched the selected streaming services.",
    )[:top_n]
    result["seed_movies"] = _enrich_media(result["seed_movies"])
    result["recommendations"] = _enrich_media(result["recommendations"])

    return LetterboxdImportResponse(
        imported_count=len(frame),
        imported_titles=frame["title"].head(10).tolist(),
        message=message,
        recommendations=result["recommendations"],
        seed_movies=result["seed_movies"],
        excluded_count=result["excluded_count"],
        warnings=warnings,
    )


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    candidate = FRONTEND_DIR / "favicon.ico"
    if candidate.exists():
        return FileResponse(candidate)
    raise HTTPException(status_code=404, detail="No favicon configured.")
