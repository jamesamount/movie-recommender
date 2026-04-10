from __future__ import annotations

from functools import lru_cache
from typing import Iterable

import requests

from backend.app.config import (
    TMDB_API_BASE_URL,
    TMDB_API_KEY,
    TMDB_API_READ_ACCESS_TOKEN,
    TMDB_WATCH_REGION,
)


class StreamingProviderError(ValueError):
    """Raised when streaming-provider lookups cannot be fulfilled."""


COMMON_PROVIDER_HINTS = [
    "Netflix",
    "Max",
    "Hulu",
    "Disney Plus",
    "Prime Video",
    "Apple TV Plus",
    "Peacock Premium",
    "Paramount Plus",
]


class TMDbStreamingProviderService:
    def __init__(self) -> None:
        self.api_base_url = TMDB_API_BASE_URL.rstrip("/")
        self.api_key = TMDB_API_KEY.strip()
        self.read_access_token = TMDB_API_READ_ACCESS_TOKEN.strip()
        self.watch_region = TMDB_WATCH_REGION
        self.session = requests.Session()
        if self.read_access_token:
            self.session.headers.update(
                {
                    "Authorization": f"Bearer {self.read_access_token}",
                    "Accept": "application/json",
                }
            )

    @property
    def enabled(self) -> bool:
        return bool(self.api_key or self.read_access_token)

    def provider_message(self) -> str:
        if self.enabled:
            return ""
        return (
            "Streaming filters are disabled until TMDB_API_READ_ACCESS_TOKEN or TMDB_API_KEY "
            "is configured on the backend."
        )

    def _request(self, path: str, *, params: dict | None = None) -> dict:
        if not self.enabled:
            raise StreamingProviderError(self.provider_message())

        request_params = dict(params or {})
        if self.api_key and not self.read_access_token:
            request_params["api_key"] = self.api_key

        response = self.session.get(
            f"{self.api_base_url}{path}",
            params=request_params,
            timeout=12,
        )

        if response.status_code == 404:
            return {}

        response.raise_for_status()
        return response.json()

    @lru_cache(maxsize=1)
    def list_providers(self) -> list[dict]:
        if not self.enabled:
            return []
        payload = self._request(
            "/watch/providers/movie",
            params={"watch_region": self.watch_region, "language": "en-US"},
        )
        providers = payload.get("results", [])
        normalized = []
        for provider in providers:
            provider_name = str(provider.get("provider_name", "")).strip()
            if not provider_name:
                continue
            normalized.append(
                {
                    "provider_id": int(provider.get("provider_id", 0)),
                    "provider_name": provider_name,
                    "logo_path": (
                        f"https://image.tmdb.org/t/p/w92{provider['logo_path']}"
                        if provider.get("logo_path")
                        else ""
                    ),
                }
            )
        return normalized

    @lru_cache(maxsize=4096)
    def movie_availability(self, tmdb_movie_id: str) -> dict:
        if not self.enabled:
            return {"streaming_services": [], "watch_link": ""}

        payload = self._request(f"/movie/{tmdb_movie_id}/watch/providers")
        region_data = payload.get("results", {}).get(self.watch_region, {})

        providers = []
        seen = set()
        for key in ("flatrate", "free", "ads"):
            for provider in region_data.get(key, []) or []:
                provider_name = str(provider.get("provider_name", "")).strip()
                if not provider_name:
                    continue
                normalized = provider_name.casefold()
                if normalized in seen:
                    continue
                seen.add(normalized)
                providers.append(provider_name)

        return {
            "streaming_services": providers,
            "watch_link": str(region_data.get("link", "")).strip(),
        }

    @lru_cache(maxsize=4096)
    def movie_visuals(self, tmdb_movie_id: str) -> dict:
        if not self.enabled:
            return {"poster_url": "", "backdrop_url": ""}

        payload = self._request(f"/movie/{tmdb_movie_id}")
        poster_path = str(payload.get("poster_path", "") or "").strip()
        backdrop_path = str(payload.get("backdrop_path", "") or "").strip()
        return {
            "poster_url": f"https://image.tmdb.org/t/p/w500{poster_path}" if poster_path else "",
            "backdrop_url": f"https://image.tmdb.org/t/p/w780{backdrop_path}" if backdrop_path else "",
        }

    def annotate_movie(self, movie: dict) -> dict:
        availability = self.movie_availability(str(movie["movie_id"]))
        enriched = dict(movie)
        enriched["streaming_services"] = availability["streaming_services"]
        enriched["watch_link"] = availability["watch_link"]
        return enriched

    def enrich_movie_media(self, movie: dict) -> dict:
        enriched = dict(movie)
        if enriched.get("poster_url") and enriched.get("backdrop_url"):
            return enriched
        visuals = self.movie_visuals(str(movie["movie_id"]))
        if not enriched.get("poster_url"):
            enriched["poster_url"] = visuals["poster_url"]
        if not enriched.get("backdrop_url"):
            enriched["backdrop_url"] = visuals["backdrop_url"]
        return enriched

    def enrich_movies_media(self, movies: Iterable[dict]) -> list[dict]:
        if not self.enabled:
            return list(movies)
        return [self.enrich_movie_media(movie) for movie in movies]

    def filter_movies(self, movies: Iterable[dict], selected_services: Iterable[str]) -> list[dict]:
        selected = {
            service.strip().casefold()
            for service in selected_services
            if str(service).strip()
        }
        if not selected:
            return list(movies)
        if not self.enabled:
            raise StreamingProviderError(self.provider_message())

        filtered = []
        for movie in movies:
            enriched = self.annotate_movie(movie)
            available = {service.casefold() for service in enriched["streaming_services"]}
            if selected & available:
                filtered.append(enriched)
        return filtered
