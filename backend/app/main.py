from __future__ import annotations

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
)
from backend.app.services.letterboxd import LetterboxdImportError, LetterboxdImporter
from backend.app.services.recommendation_service import get_recommendation_engine
from ml.recommender import RecommendationError

app = FastAPI(
    title="CineMatch ML",
    description="A portfolio-ready movie recommendation engine using content features, cosine similarity, and k-NN retrieval.",
    version="1.0.0",
)

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
    return HealthResponse(
        status="ok",
        dataset_source=filters["dataset_source"],
        demo_mode=filters["demo_mode"],
        movie_count=filters["movie_count"],
        genres=filters["genres"],
        decades=filters["decades"],
        model_version=engine.artifact["model_version"],
    )


@app.get("/search", response_model=SearchResponse)
def search_movies(
    q: str = Query(..., min_length=1),
    limit: int = Query(12, ge=1, le=30),
    genre: str | None = Query(None),
    decade: int | None = Query(None),
    min_rating: float | None = Query(None, ge=0, le=10),
    runtime_max: int | None = Query(None, ge=1),
) -> SearchResponse:
    engine = get_recommendation_engine()
    results = engine.search(
        q,
        limit=limit,
        genre=genre,
        decade=decade,
        min_rating=min_rating,
        runtime_max=runtime_max,
    )
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
) -> SimilarResponse:
    engine = get_recommendation_engine()
    try:
        payload = engine.similar_movies(
            movie_id=movie_id,
            title=title,
            method=method,
            top_n=top_n,
            genre=genre,
            decade=decade,
            min_rating=min_rating,
            runtime_max=runtime_max,
        )
    except RecommendationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return SimilarResponse(method=method, **payload)


@app.get("/recommend/random", response_model=RandomResponse)
def recommend_random(
    genre: str | None = Query(None),
    decade: int | None = Query(None),
    min_rating: float | None = Query(None, ge=0, le=10),
    runtime_max: int | None = Query(None, ge=1),
) -> RandomResponse:
    engine = get_recommendation_engine()
    try:
        movie = engine.random_movie(
            genre=genre,
            decade=decade,
            min_rating=min_rating,
            runtime_max=runtime_max,
        )
    except RecommendationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return RandomResponse(movie=movie)


@app.post("/recommend/personalized", response_model=PersonalizedResponse)
def recommend_personalized(payload: PersonalizedRequest) -> PersonalizedResponse:
    engine = get_recommendation_engine()
    try:
        result = engine.personalized_recommendations(
            favorite_titles=payload.favorite_titles,
            rated_movies=[entry.model_dump() for entry in payload.rated_movies],
            top_n=payload.top_n,
            genre=payload.genre,
            decade=payload.decade,
            min_rating=payload.min_rating,
            runtime_max=payload.runtime_max,
        )
    except RecommendationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
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
            top_n=top_n,
            genre=genre,
            decade=decade,
            min_rating=min_rating,
            runtime_max=runtime_max,
        )
    except LetterboxdImportError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except RecommendationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

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
