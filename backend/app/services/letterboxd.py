from __future__ import annotations

import io
import os
from typing import Any

import pandas as pd


class LetterboxdImportError(ValueError):
    """Raised for invalid or unsupported Letterboxd inputs."""


class LetterboxdImporter:
    SUPPORTED_NAME_COLUMNS = ("Name", "name", "Title", "title")
    SUPPORTED_YEAR_COLUMNS = ("Year", "year")
    SUPPORTED_RATING_COLUMNS = ("Rating", "rating")
    SUPPORTED_URI_COLUMNS = ("Letterboxd URI", "LetterboxdURI", "url")

    def parse_csv_bytes(self, payload: bytes) -> pd.DataFrame:
        if not payload:
            raise LetterboxdImportError("The uploaded Letterboxd file was empty.")
        try:
            frame = pd.read_csv(io.BytesIO(payload))
        except Exception as exc:  # pragma: no cover - defensive parsing
            raise LetterboxdImportError("Could not parse the uploaded CSV file.") from exc
        return self._normalize_frame(frame)

    def parse_csv_text(self, payload: str) -> pd.DataFrame:
        if not payload.strip():
            raise LetterboxdImportError("Paste CSV text or upload a CSV export.")
        try:
            frame = pd.read_csv(io.StringIO(payload))
        except Exception as exc:  # pragma: no cover - defensive parsing
            raise LetterboxdImportError("Could not parse the pasted CSV text.") from exc
        return self._normalize_frame(frame)

    def scrape_public_username(self, username: str) -> pd.DataFrame:
        if not username.strip():
            raise LetterboxdImportError("Enter a public Letterboxd username or upload a CSV export.")
        if os.getenv("ENABLE_LETTERBOXD_SCRAPING") != "1":
            raise LetterboxdImportError(
                "Public username scraping is disabled by default. "
                "Letterboxd has no official public API, so CSV export import is the reliable path."
            )
        raise LetterboxdImportError(
            "Username scraping is intentionally left opt-in and unimplemented in this starter "
            "because Letterboxd markup changes frequently. Use CSV export import instead."
        )

    def to_personalization_payload(self, frame: pd.DataFrame) -> tuple[list[str], list[dict[str, Any]]]:
        if frame.empty:
            raise LetterboxdImportError("The Letterboxd import did not contain any movie rows.")

        rated = frame.dropna(subset=["title"]).copy()
        rated["rating"] = pd.to_numeric(rated["rating"], errors="coerce")
        rated["rating"] = rated["rating"].fillna(4.0)

        favorites = rated[rated["rating"] >= rated["rating"].quantile(0.8)]["title"].tolist()
        rated_movies = [
            {
                "title": row["title"],
                "year": int(row["year"]) if pd.notna(row["year"]) else None,
                "rating": float(row["rating"]),
            }
            for _, row in rated.iterrows()
        ]
        return favorites[:12], rated_movies

    def _normalize_frame(self, frame: pd.DataFrame) -> pd.DataFrame:
        name_column = self._first_present(frame, self.SUPPORTED_NAME_COLUMNS)
        if not name_column:
            raise LetterboxdImportError(
                "CSV import requires a Name or Title column from a Letterboxd export."
            )
        year_column = self._first_present(frame, self.SUPPORTED_YEAR_COLUMNS)
        rating_column = self._first_present(frame, self.SUPPORTED_RATING_COLUMNS)
        uri_column = self._first_present(frame, self.SUPPORTED_URI_COLUMNS)

        normalized = pd.DataFrame()
        normalized["title"] = frame[name_column].astype(str).str.strip()
        normalized["year"] = pd.to_numeric(frame[year_column], errors="coerce") if year_column else None
        normalized["rating"] = (
            pd.to_numeric(frame[rating_column], errors="coerce") if rating_column else 4.0
        )
        normalized["letterboxd_uri"] = frame[uri_column].astype(str) if uri_column else ""
        normalized = normalized[normalized["title"].ne("")]
        normalized = normalized.drop_duplicates(subset=["title", "year"], keep="first")
        return normalized.reset_index(drop=True)

    def _first_present(self, frame: pd.DataFrame, candidates: tuple[str, ...]) -> str | None:
        for candidate in candidates:
            if candidate in frame.columns:
                return candidate
        return None

