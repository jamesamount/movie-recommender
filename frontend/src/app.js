import React, {
  startTransition,
  useDeferredValue,
  useEffect,
  useState,
} from "react";
import htm from "htm";

import {
  getHealth,
  getPersonalizedRecommendations,
  getRandomMovie,
  getSimilarMovies,
  importLetterboxd,
  searchMovies,
} from "./api.js";

const html = htm.bind(React.createElement);

const emptyFilters = {
  genre: "",
  decade: "",
  minRating: "",
  runtimeMax: "",
};

function formatGenres(genres = []) {
  return genres.join(" • ");
}

function parseFavorites(text) {
  return text
    .split(",")
    .map((item) => item.trim())
    .filter(Boolean);
}

function parseRatedMovies(text) {
  return text
    .split("\n")
    .map((line) => line.trim())
    .filter(Boolean)
    .map((line) => {
      const [title, rating] = line.split("|").map((part) => part.trim());
      const numericRating = Number(rating);
      return {
        title,
        rating: Number.isFinite(numericRating) ? numericRating : 4,
      };
    })
    .filter((entry) => entry.title);
}

function toApiFilters(filters) {
  return {
    genre: filters.genre || undefined,
    decade: filters.decade ? Number(filters.decade) : undefined,
    min_rating: filters.minRating ? Number(filters.minRating) : undefined,
    runtime_max: filters.runtimeMax ? Number(filters.runtimeMax) : undefined,
  };
}

function LoadingBlock({ label = "Loading..." }) {
  return html`<div className="loading-block">${label}</div>`;
}

function InlineError({ message }) {
  if (!message) return null;
  return html`<div className="inline-error">${message}</div>`;
}

function MovieCard({ movie, badge, onSelect, actionLabel = "Find similar" }) {
  const posterStyle = movie.poster_url
    ? { backgroundImage: `linear-gradient(180deg, rgba(6, 10, 14, 0.18), rgba(6, 10, 14, 0.78)), url(${movie.poster_url})` }
    : undefined;

  return html`
    <article className="movie-card">
      <div className="movie-card__poster" style=${posterStyle}>
        ${movie.poster_url
          ? null
          : html`
              <div className="poster-fallback">
                <span className="poster-fallback__year">${movie.year || "Now"}</span>
                <strong>${movie.title}</strong>
              </div>
            `}
        ${badge ? html`<span className="movie-card__badge">${badge}</span>` : null}
      </div>
      <div className="movie-card__body">
        <div className="movie-card__meta">
          <p className="movie-card__eyebrow">${movie.year || "Unknown year"} • ${movie.runtime || "?"} min</p>
          <h3>${movie.title}</h3>
          <p className="movie-card__genres">${formatGenres(movie.genres)}</p>
        </div>
        <div className="movie-card__stats">
          <span>TMDb ${movie.rating?.toFixed?.(1) || movie.rating}</span>
          <span>User ${movie.user_rating?.toFixed?.(1) || movie.user_rating}</span>
          ${movie.similarity ? html`<span>Match ${(movie.similarity * 100).toFixed(0)}%</span>` : null}
        </div>
        <p className="movie-card__overview">${movie.overview}</p>
        <div className="movie-card__footer">
          <span>Dir. ${movie.director || "Unknown"}</span>
          ${onSelect
            ? html`
                <button className="secondary-button" onClick=${() => onSelect(movie)}>
                  ${actionLabel}
                </button>
              `
            : null}
        </div>
      </div>
    </article>
  `;
}

function FilterBar({ health, filters, onChange, onReset }) {
  return html`
    <section className="filter-bar">
      <div className="filter-bar__heading">
        <p className="section-kicker">Tuning</p>
        <h2>Shape discovery with practical filters</h2>
      </div>
      <div className="filter-grid">
        <label>
          <span>Genre</span>
          <select
            value=${filters.genre}
            onChange=${(event) => onChange("genre", event.target.value)}
          >
            <option value="">All genres</option>
            ${(health?.genres || []).map(
              (genre) => html`<option value=${genre}>${genre}</option>`
            )}
          </select>
        </label>
        <label>
          <span>Decade</span>
          <select
            value=${filters.decade}
            onChange=${(event) => onChange("decade", event.target.value)}
          >
            <option value="">Any decade</option>
            ${(health?.decades || []).map(
              (decade) => html`<option value=${decade}>${decade}s</option>`
            )}
          </select>
        </label>
        <label>
          <span>Minimum TMDb rating</span>
          <input
            type="number"
            min="0"
            max="10"
            step="0.1"
            value=${filters.minRating}
            onInput=${(event) => onChange("minRating", event.target.value)}
            placeholder="7.0"
          />
        </label>
        <label>
          <span>Runtime cap</span>
          <input
            type="number"
            min="60"
            max="300"
            step="1"
            value=${filters.runtimeMax}
            onInput=${(event) => onChange("runtimeMax", event.target.value)}
            placeholder="150"
          />
        </label>
      </div>
      <button className="ghost-button" onClick=${onReset}>Reset filters</button>
    </section>
  `;
}

function SearchSection({
  query,
  setQuery,
  results,
  loading,
  error,
  onSelectMovie,
  selectedMovie,
  similarResults,
  similarMethod,
  setSimilarMethod,
  similarLoading,
}) {
  return html`
    <section className="panel panel--search">
      <div className="panel__header">
        <div>
          <p className="section-kicker">Search + Retrieval</p>
          <h2>Start with a movie, then expand outward</h2>
        </div>
        <p className="panel__copy">
          Search across titles, directors, and overviews. Each picked title can branch into cosine similarity
          or k-nearest-neighbor recommendations.
        </p>
      </div>

      <div className="search-shell">
        <input
          className="search-input"
          value=${query}
          onInput=${(event) => setQuery(event.target.value)}
          placeholder="Search for Interstellar, Parasite, Greta Gerwig, cyberpunk..."
        />
      </div>

      <${InlineError} message=${error} />

      <div className="search-results">
        <div>
          <div className="mini-heading">
            <h3>Matches</h3>
            <span>${results.length} loaded</span>
          </div>
          ${loading
            ? html`<${LoadingBlock} label="Searching the catalog..." />`
            : html`
                <div className="movie-grid movie-grid--compact">
                  ${results.map(
                    (movie) => html`
                      <${MovieCard}
                        movie=${movie}
                        onSelect=${onSelectMovie}
                      />
                    `
                  )}
                </div>
              `}
        </div>

        <div className="recommendation-column">
          <div className="mini-heading mini-heading--stacked">
            <div>
              <h3>Similar picks</h3>
              <span>${selectedMovie ? `Seeded by ${selectedMovie.title}` : "Choose a movie to populate this section"}</span>
            </div>
            <div className="toggle-row">
              <button
                className=${similarMethod === "cosine" ? "toggle-button is-active" : "toggle-button"}
                onClick=${() => setSimilarMethod("cosine")}
              >
                Cosine
              </button>
              <button
                className=${similarMethod === "knn" ? "toggle-button is-active" : "toggle-button"}
                onClick=${() => setSimilarMethod("knn")}
              >
                k-NN
              </button>
            </div>
          </div>
          ${similarLoading
            ? html`<${LoadingBlock} label="Ranking neighbors..." />`
            : html`
                <div className="movie-grid movie-grid--compact">
                  ${(similarResults || []).map(
                    (movie, index) => html`
                      <${MovieCard}
                        movie=${movie}
                        badge=${`#${index + 1}`}
                      />
                    `
                  )}
                </div>
              `}
        </div>
      </div>
    </section>
  `;
}

function SurpriseSection({ movie, loading, error, onRefresh }) {
  return html`
    <section className="panel panel--surprise">
      <div className="panel__header">
        <div>
          <p className="section-kicker">Discovery</p>
          <h2>Surprise me with something worth watching</h2>
        </div>
        <button className="primary-button" onClick=${onRefresh}>Roll a random movie</button>
      </div>
      <${InlineError} message=${error} />
      ${loading
        ? html`<${LoadingBlock} label="Pulling a high-quality random pick..." />`
        : movie
          ? html`<${MovieCard} movie=${movie} actionLabel="" />`
          : null}
    </section>
  `;
}

function PersonalizationSection({
  favoriteTitles,
  setFavoriteTitles,
  ratedMoviesText,
  setRatedMoviesText,
  loading,
  error,
  results,
  onSubmit,
}) {
  return html`
    <section className="panel">
      <div className="panel__header">
        <div>
          <p className="section-kicker">Personalization</p>
          <h2>Build a taste profile from favorites or top ratings</h2>
        </div>
        <p className="panel__copy">
          Favorites act as anchors. Ratings let the model weight the profile, average the feature vectors, and
          exclude movies you already know.
        </p>
      </div>

      <div className="form-grid">
        <label>
          <span>Favorite movies</span>
          <textarea
            rows="3"
            value=${favoriteTitles}
            onInput=${(event) => setFavoriteTitles(event.target.value)}
            placeholder="Inception, Arrival, Before Sunrise"
          ></textarea>
        </label>
        <label>
          <span>Rated movies</span>
          <textarea
            rows="6"
            value=${ratedMoviesText}
            onInput=${(event) => setRatedMoviesText(event.target.value)}
            placeholder=${"Mad Max: Fury Road | 5\nHer | 4.5\nMoonlight | 5"}
          ></textarea>
        </label>
      </div>

      <div className="button-row">
        <button className="primary-button" onClick=${onSubmit}>
          Get personalized recommendations
        </button>
      </div>

      <${InlineError} message=${error} />

      ${loading
        ? html`<${LoadingBlock} label="Learning your taste profile..." />`
        : results
          ? html`
              <div className="personalized-meta">
                <strong>Seed movies:</strong> ${results.seed_movies.map((movie) => movie.title).join(", ")}
              </div>
              <div className="movie-grid">
                ${results.recommendations.map(
                  (movie, index) => html`<${MovieCard} movie=${movie} badge=${`For You ${index + 1}`} />`
                )}
              </div>
            `
          : null}
    </section>
  `;
}

function LetterboxdSection({
  username,
  setUsername,
  csvText,
  setCsvText,
  file,
  setFile,
  loading,
  error,
  result,
  onSubmit,
}) {
  return html`
    <section className="panel">
      <div className="panel__header">
        <div>
          <p className="section-kicker">Letterboxd Import</p>
          <h2>Bring in exports without pretending there is an official public API</h2>
        </div>
        <p className="panel__copy">
          CSV upload is the reliable path. Public username scraping is left disabled by default and fails
          gracefully because the HTML surface is unofficial and fragile.
        </p>
      </div>

      <div className="form-grid">
        <label>
          <span>Public username</span>
          <input
            type="text"
            value=${username}
            onInput=${(event) => setUsername(event.target.value)}
            placeholder="optionalusername"
          />
        </label>
        <label>
          <span>Letterboxd CSV export</span>
          <input
            type="file"
            accept=".csv,text/csv"
            onChange=${(event) => setFile(event.target.files?.[0] || null)}
          />
          <small>${file ? `Selected: ${file.name}` : "Upload ratings, diary, or watch history CSV."}</small>
        </label>
      </div>

      <label>
        <span>Or paste CSV text</span>
        <textarea
          rows="5"
          value=${csvText}
          onInput=${(event) => setCsvText(event.target.value)}
          placeholder="Name,Year,Rating&#10;Arrival,2016,5&#10;Whiplash,2014,4.5"
        ></textarea>
      </label>

      <div className="button-row">
        <button className="primary-button" onClick=${onSubmit}>Import Letterboxd data</button>
      </div>

      <${InlineError} message=${error} />

      ${loading
        ? html`<${LoadingBlock} label="Parsing Letterboxd data..." />`
        : result
          ? html`
              <div className="letterboxd-summary">
                <p>${result.message}</p>
                <p>Imported titles: ${result.imported_titles.join(", ")}</p>
              </div>
              <div className="movie-grid">
                ${result.recommendations.map(
                  (movie, index) => html`<${MovieCard} movie=${movie} badge=${`LBXD ${index + 1}`} />`
                )}
              </div>
            `
          : null}
    </section>
  `;
}

export function App() {
  const [health, setHealth] = useState(null);
  const [appError, setAppError] = useState("");

  const [filters, setFilters] = useState(emptyFilters);

  const [query, setQuery] = useState("Interstellar");
  const deferredQuery = useDeferredValue(query);
  const [searchResults, setSearchResults] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState("");

  const [selectedMovie, setSelectedMovie] = useState(null);
  const [similarMethod, setSimilarMethod] = useState("cosine");
  const [similarResults, setSimilarResults] = useState([]);
  const [similarLoading, setSimilarLoading] = useState(false);

  const [randomMovie, setRandomMovie] = useState(null);
  const [randomLoading, setRandomLoading] = useState(false);
  const [randomError, setRandomError] = useState("");

  const [favoriteTitles, setFavoriteTitles] = useState("Arrival, Her, Moonlight");
  const [ratedMoviesText, setRatedMoviesText] = useState("Arrival | 5\nMoonlight | 5\nHer | 4.5");
  const [personalizedLoading, setPersonalizedLoading] = useState(false);
  const [personalizedError, setPersonalizedError] = useState("");
  const [personalizedResults, setPersonalizedResults] = useState(null);

  const [letterboxdUsername, setLetterboxdUsername] = useState("");
  const [letterboxdCsvText, setLetterboxdCsvText] = useState("");
  const [letterboxdFile, setLetterboxdFile] = useState(null);
  const [letterboxdLoading, setLetterboxdLoading] = useState(false);
  const [letterboxdError, setLetterboxdError] = useState("");
  const [letterboxdResult, setLetterboxdResult] = useState(null);

  useEffect(() => {
    async function loadHealth() {
      try {
        const payload = await getHealth();
        setHealth(payload);
      } catch (error) {
        setAppError(error.message);
      }
    }

    loadHealth();
  }, []);

  useEffect(() => {
    async function runSearch() {
      if (!deferredQuery.trim()) {
        startTransition(() => {
          setSearchResults([]);
          setSelectedMovie(null);
          setSimilarResults([]);
        });
        return;
      }

      try {
        setSearchLoading(true);
        setSearchError("");
        const filterPayload = toApiFilters(filters);
        const payload = await searchMovies({
          q: deferredQuery,
          limit: 8,
          ...filterPayload,
        });
        startTransition(() => {
          setSearchResults(payload.results);
          if (payload.results.length) {
            setSelectedMovie(payload.results[0]);
          } else {
            setSelectedMovie(null);
            setSimilarResults([]);
          }
        });
      } catch (error) {
        setSearchError(error.message);
      } finally {
        setSearchLoading(false);
      }
    }

    runSearch();
  }, [deferredQuery, filters.genre, filters.decade, filters.minRating, filters.runtimeMax]);

  useEffect(() => {
    async function runSimilar() {
      if (!selectedMovie?.movie_id) return;
      try {
        setSimilarLoading(true);
        const filterPayload = toApiFilters(filters);
        const payload = await getSimilarMovies({
          movie_id: selectedMovie.movie_id,
          method: similarMethod,
          top_n: 6,
          ...filterPayload,
        });
        startTransition(() => {
          setSimilarResults(payload.recommendations);
        });
      } catch (error) {
        setSearchError(error.message);
      } finally {
        setSimilarLoading(false);
      }
    }

    runSimilar();
  }, [selectedMovie, similarMethod, filters.genre, filters.decade, filters.minRating, filters.runtimeMax]);

  useEffect(() => {
    refreshRandomMovie();
  }, [filters.genre, filters.decade, filters.minRating, filters.runtimeMax]);

  async function refreshRandomMovie() {
    try {
      setRandomLoading(true);
      setRandomError("");
      const payload = await getRandomMovie(toApiFilters(filters));
      setRandomMovie(payload.movie);
    } catch (error) {
      setRandomError(error.message);
    } finally {
      setRandomLoading(false);
    }
  }

  async function handlePersonalizedSubmit() {
    try {
      setPersonalizedLoading(true);
      setPersonalizedError("");
      const payload = await getPersonalizedRecommendations({
        favorite_titles: parseFavorites(favoriteTitles),
        rated_movies: parseRatedMovies(ratedMoviesText),
        top_n: 8,
        ...toApiFilters(filters),
      });
      setPersonalizedResults(payload);
    } catch (error) {
      setPersonalizedError(error.message);
    } finally {
      setPersonalizedLoading(false);
    }
  }

  async function handleLetterboxdSubmit() {
    try {
      setLetterboxdLoading(true);
      setLetterboxdError("");
      const formData = new FormData();
      if (letterboxdFile) {
        formData.set("file", letterboxdFile);
      }
      if (letterboxdCsvText.trim()) {
        formData.set("csv_text", letterboxdCsvText);
      }
      if (letterboxdUsername.trim()) {
        formData.set("username", letterboxdUsername.trim());
      }
      formData.set("top_n", "8");
      Object.entries(toApiFilters(filters)).forEach(([key, value]) => {
        if (value !== undefined && value !== null && value !== "") {
          formData.set(key, String(value));
        }
      });

      const payload = await importLetterboxd(formData);
      setLetterboxdResult(payload);
    } catch (error) {
      setLetterboxdError(error.message);
    } finally {
      setLetterboxdLoading(false);
    }
  }

  function updateFilter(key, value) {
    setFilters((current) => ({ ...current, [key]: value }));
  }

  return html`
    <div className="page-shell">
      <header className="hero">
        <div className="hero__copy">
          <p className="hero__eyebrow">CineMatch ML</p>
          <h1>Movie recommendations that actually show the machine learning.</h1>
          <p className="hero__lede">
            Content features, cosine similarity, nearest neighbors, quality-aware reranking, and practical
            personalization from favorites or Letterboxd exports.
          </p>
          <div className="hero__chips">
            <span>TF-IDF metadata embeddings</span>
            <span>k-NN retrieval</span>
            <span>Letterboxd CSV personalization</span>
            <span>FastAPI + React</span>
          </div>
        </div>

        <div className="hero__stats">
          <div className="stat-card">
            <span>Catalog</span>
            <strong>${health?.movie_count || "..."}</strong>
          </div>
          <div className="stat-card">
            <span>Dataset mode</span>
            <strong>${health?.demo_mode ? "Offline demo" : "Full dataset"}</strong>
          </div>
          <div className="stat-card">
            <span>Source</span>
            <strong>${health?.dataset_source || "Loading..."}</strong>
          </div>
        </div>
      </header>

      <${InlineError} message=${appError} />
      <${FilterBar}
        health=${health}
        filters=${filters}
        onChange=${updateFilter}
        onReset=${() => setFilters({ ...emptyFilters })}
      />

      <main className="content-grid">
        <div className="content-grid__main">
          <${SearchSection}
            query=${query}
            setQuery=${setQuery}
            results=${searchResults}
            loading=${searchLoading}
            error=${searchError}
            onSelectMovie=${setSelectedMovie}
            selectedMovie=${selectedMovie}
            similarResults=${similarResults}
            similarMethod=${similarMethod}
            setSimilarMethod=${setSimilarMethod}
            similarLoading=${similarLoading}
          />
          <${PersonalizationSection}
            favoriteTitles=${favoriteTitles}
            setFavoriteTitles=${setFavoriteTitles}
            ratedMoviesText=${ratedMoviesText}
            setRatedMoviesText=${setRatedMoviesText}
            loading=${personalizedLoading}
            error=${personalizedError}
            results=${personalizedResults}
            onSubmit=${handlePersonalizedSubmit}
          />
        </div>
        <div className="content-grid__side">
          <${SurpriseSection}
            movie=${randomMovie}
            loading=${randomLoading}
            error=${randomError}
            onRefresh=${refreshRandomMovie}
          />
          <${LetterboxdSection}
            username=${letterboxdUsername}
            setUsername=${setLetterboxdUsername}
            csvText=${letterboxdCsvText}
            setCsvText=${setLetterboxdCsvText}
            file=${letterboxdFile}
            setFile=${setLetterboxdFile}
            loading=${letterboxdLoading}
            error=${letterboxdError}
            result=${letterboxdResult}
            onSubmit=${handleLetterboxdSubmit}
          />
        </div>
      </main>
    </div>
  `;
}
