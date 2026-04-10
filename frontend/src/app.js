import React, {
  startTransition,
  useEffect,
  useState,
} from "react";
import htm from "htm";

import {
  getHealth,
  getPersonalizedRecommendations,
  getRandomMovie,
  getSimilarMovies,
  getStreamingProviders,
  importLetterboxd,
  searchMovies,
} from "./api.js";

const html = htm.bind(React.createElement);

const emptyFilters = {
  genre: "",
  decade: "",
  minRating: "",
  runtimeMax: "",
  streamingServices: "",
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
    streaming_services: filters.streamingServices || undefined,
  };
}

function hasActiveFilters(filters) {
  return Object.values(filters).some((value) => String(value || "").trim() !== "");
}

function formatImportedTitles(titles = [], limit = 10) {
  if (!titles.length) return "";
  const visible = titles.slice(0, limit).join(", ");
  const remaining = titles.length - limit;
  return remaining > 0 ? `${visible}, and ${remaining} more` : visible;
}

function LoadingBlock({ label = "Loading..." }) {
  return html`<div className="loading-block">${label}</div>`;
}

function InlineError({ message }) {
  if (!message) return null;
  return html`<div className="inline-error">${message}</div>`;
}

function MediaArtwork({ src, alt, className, onError }) {
  if (!src) return null;
  return html`<img className=${className} src=${src} alt=${alt} loading="lazy" onError=${onError} />`;
}

function FeatureBanner({ movie, eyebrow = "Featured" }) {
  const [bannerFailed, setBannerFailed] = useState(false);
  const bannerSrc = !bannerFailed ? (movie?.backdrop_url || movie?.poster_url || "") : "";

  if (!movie) return null;

  return html`
    <section className="feature-banner">
      ${bannerSrc
        ? html`
            <${MediaArtwork}
              src=${bannerSrc}
              alt=${movie.title}
              className="feature-banner__image"
              onError=${() => setBannerFailed(true)}
            />
          `
        : null}
      <div className="feature-banner__overlay"></div>
      <div className="feature-banner__content">
        <p className="section-kicker">${eyebrow}</p>
        <h3>${movie.title}</h3>
        <p>${movie.overview}</p>
      </div>
    </section>
  `;
}

function PosterTile({ movie, onSelect, isActive = false, label }) {
  const [imageFailed, setImageFailed] = useState(false);
  const imageSrc = !imageFailed ? (movie.poster_url || movie.backdrop_url || "") : "";

  return html`
    <button
      className=${isActive ? "poster-tile is-active" : "poster-tile"}
      onClick=${() => onSelect?.(movie)}
      type="button"
    >
      <div className="poster-tile__image-wrap">
        ${imageSrc
          ? html`
              <${MediaArtwork}
                src=${imageSrc}
                alt=${movie.title}
                className="poster-tile__image"
                onError=${() => setImageFailed(true)}
              />
            `
          : html`<div className="poster-tile__fallback"></div>`}
        ${label ? html`<span className="poster-tile__label">${label}</span>` : null}
      </div>
      <div className="poster-tile__body">
        <strong>${movie.title}</strong>
        <span>${movie.year || "Unknown"}${movie.genres?.[0] ? ` • ${movie.genres[0]}` : ""}</span>
      </div>
    </button>
  `;
}

function CompactMovieRow({ movie, badge, onSelect, actionLabel = "Use as seed" }) {
  const [imageFailed, setImageFailed] = useState(false);
  const imageSrc = !imageFailed ? (movie.backdrop_url || movie.poster_url || "") : "";

  return html`
    <article className="compact-card">
      <div className="compact-card__thumb">
        ${imageSrc
          ? html`
              <${MediaArtwork}
                src=${imageSrc}
                alt=${movie.title}
                className="compact-card__image"
                onError=${() => setImageFailed(true)}
              />
            `
          : html`<div className="compact-card__fallback"></div>`}
        ${badge ? html`<span className="compact-card__badge">${badge}</span>` : null}
      </div>
      <div className="compact-card__body">
        <div className="compact-card__copy">
          <p className="compact-card__eyebrow">
            ${movie.year || "Unknown"}${movie.runtime ? ` • ${movie.runtime} min` : ""}
          </p>
          <h4>${movie.title}</h4>
          <p className="compact-card__genres">${formatGenres(movie.genres)}</p>
          <div className="compact-card__stats">
            <span>TMDb ${movie.rating?.toFixed?.(1) || movie.rating}</span>
            ${movie.similarity ? html`<span>Match ${(movie.similarity * 100).toFixed(0)}%</span>` : null}
          </div>
        </div>
        ${onSelect
          ? html`
              <button className="compact-card__action" onClick=${() => onSelect(movie)} type="button">
                ${actionLabel}
              </button>
            `
          : null}
      </div>
    </article>
  `;
}

function SectionHeader({ kicker, title, detail, actions }) {
  return html`
    <div className="section-header">
      <div>
        ${kicker ? html`<p className="section-kicker">${kicker}</p>` : null}
        <h3>${title}</h3>
        ${detail ? html`<p className="section-detail">${detail}</p>` : null}
      </div>
      ${actions ? html`<div className="section-header__actions">${actions}</div>` : null}
    </div>
  `;
}

function MovieCard({ movie, badge, onSelect, actionLabel = "Find similar" }) {
  const [posterFailed, setPosterFailed] = useState(false);
  const posterHue = Math.abs(
    Array.from(`${movie.title}${movie.year || ""}`).reduce(
      (accumulator, character) => accumulator + character.charCodeAt(0),
      0
    )
  ) % 360;
  const artworkSrc = !posterFailed ? (movie.poster_url || movie.backdrop_url || "") : "";
  const posterStyle = artworkSrc
    ? {
        backgroundImage: "linear-gradient(180deg, rgba(6, 10, 14, 0.08), rgba(6, 10, 14, 0.4))",
      }
    : {
        backgroundImage: `linear-gradient(160deg, hsla(${posterHue}, 70%, 58%, 0.65), hsla(${
          (posterHue + 48) % 360
        }, 65%, 38%, 0.42)), radial-gradient(circle at top right, rgba(255,255,255,0.18), transparent 36%), linear-gradient(180deg, #20313b, #121a20)`,
      };

  return html`
    <article className="movie-card">
      <div className="movie-card__poster" style=${posterStyle}>
        ${artworkSrc
          ? html`
              <${MediaArtwork}
                src=${artworkSrc}
                alt=${movie.title}
                className="movie-card__image"
                onError=${() => setPosterFailed(true)}
              />
            `
          : null}
        ${artworkSrc
          ? null
          : html`
              <div className="poster-fallback">
                <span className="poster-fallback__year">${movie.year || "Now"}</span>
                <strong>${movie.title}</strong>
                <span className="poster-fallback__genre">${movie.genres?.[0] || "Feature Film"}</span>
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
          ${movie.user_rating > 0 ? html`<span>User ${movie.user_rating?.toFixed?.(1) || movie.user_rating}</span>` : null}
          ${movie.similarity ? html`<span>Match ${(movie.similarity * 100).toFixed(0)}%</span>` : null}
        </div>
        ${movie.streaming_services?.length
          ? html`
              <div className="movie-card__services">
                ${movie.streaming_services.slice(0, 4).map(
                  (service) => html`<span>${service}</span>`
                )}
              </div>
            `
          : null}
        <p className="movie-card__overview">${movie.overview}</p>
        <div className="movie-card__footer">
          <span>Dir. ${movie.director || "Unknown"}</span>
          <div className="movie-card__actions">
            ${movie.watch_link
              ? html`
                  <a className="secondary-button secondary-button--link" href=${movie.watch_link} target="_blank" rel="noreferrer">
                    Where to watch
                  </a>
                `
              : null}
            ${onSelect
              ? html`
                  <button className="secondary-button" onClick=${() => onSelect(movie)}>
                    ${actionLabel}
                  </button>
                `
              : null}
          </div>
        </div>
      </div>
    </article>
  `;
}

function parseStreamingServices(text) {
  return text
    .split(",")
    .map((service) => service.trim())
    .filter(Boolean);
}

function toggleProvider(filters, onChange, providerName) {
  const selected = new Set(parseStreamingServices(filters.streamingServices));
  if (selected.has(providerName)) {
    selected.delete(providerName);
  } else {
    selected.add(providerName);
  }
  onChange("streamingServices", Array.from(selected).join(", "));
}

function FilterBar({ health, filters, onChange, onReset, streamingProviders }) {
  const selectedProviders = new Set(parseStreamingServices(filters.streamingServices));
  const filtersActive = hasActiveFilters(filters);
  return html`
    <section className="filter-bar">
      <div className="filter-bar__heading">
        <div className="filter-bar__title">
          <p className="section-kicker">Tuning</p>
          <h2>Shape discovery with practical filters</h2>
        </div>
        ${filtersActive ? html`<span className="active-filter-badge">Filters active</span>` : null}
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
      <label className="streaming-field">
        <span>Streaming services you have</span>
        <input
          type="text"
          value=${filters.streamingServices}
          onInput=${(event) => onChange("streamingServices", event.target.value)}
          placeholder="Netflix, Hulu, Max, Disney Plus"
          disabled=${streamingProviders && !streamingProviders.enabled}
        />
        <small>
          ${streamingProviders?.enabled
            ? `Filter titles by streaming availability in ${streamingProviders.watch_region}.`
            : streamingProviders?.message || "Streaming filters are unavailable right now."}
        </small>
      </label>
      ${streamingProviders?.providers?.length
        ? html`
            <div className="provider-chip-row">
              ${streamingProviders.providers.slice(0, 16).map(
                (provider) => html`
                  <button
                    className=${selectedProviders.has(provider.provider_name) ? "provider-chip is-active" : "provider-chip"}
                    onClick=${() => toggleProvider(filters, onChange, provider.provider_name)}
                    type="button"
                  >
                    ${provider.provider_name}
                  </button>
                `
              )}
            </div>
          `
        : null}
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
  seedMovie,
  similarMethod,
  setSimilarMethod,
  similarLoading,
  similarError,
}) {
  const visibleResults = results.slice(0, 6);
  const featuredRecommendation = similarResults?.[0] || null;
  const quickPicks = (similarResults || []).slice(1, 6);

  return html`
    <section className="panel panel--search">
      <div className="panel__header panel__header--stacked">
        <div>
          <p className="section-kicker">Search + Retrieval</p>
          <h2>Start with one title, then open a cleaner recommendation shelf</h2>
        </div>
        <p className="panel__copy">
          Search across titles, directors, and overviews. Pick a result to branch into cosine similarity or
          k-nearest-neighbor recommendations without dumping a huge list on screen.
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
      ${loading
        ? html`<${LoadingBlock} label="Searching the catalog..." />`
        : visibleResults.length
          ? html`
              <div className="search-pills">
                ${visibleResults.map(
                  (movie) => html`
                    <button
                      className=${selectedMovie?.movie_id === movie.movie_id ? "search-pill is-active" : "search-pill"}
                      onClick=${() => onSelectMovie(movie)}
                      type="button"
                    >
                      <strong>${movie.title}</strong>
                      <span>${movie.year || "Unknown"}${movie.genres?.[0] ? ` • ${movie.genres[0]}` : ""}</span>
                    </button>
                  `
                )}
              </div>
            `
          : null}
      <div className="cinema-layout">
        <div className="cinema-layout__main">
          ${seedMovie ? html`<${FeatureBanner} movie=${seedMovie} eyebrow="Current seed" />` : null}
        </div>

        <div className="cinema-layout__side">
          <${SectionHeader}
            title="Top similar picks"
            detail=${selectedMovie ? `Seeded by ${selectedMovie.title}` : "Choose a result to generate this shelf."}
            actions=${html`
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
            `}
          />
          <${InlineError} message=${similarError} />
          ${similarLoading
            ? html`<${LoadingBlock} label="Ranking neighbors..." />`
            : html`
                ${featuredRecommendation
                  ? html`<${FeatureBanner} movie=${featuredRecommendation} eyebrow="Top match" />`
                  : html`<div className="empty-state">Choose a movie to populate this recommendation shelf.</div>`}
                <div className="compact-card-list">
                  ${quickPicks.map(
                    (movie, index) => html`
                      <${CompactMovieRow}
                        movie=${movie}
                        badge=${`#${index + 2}`}
                        onSelect=${onSelectMovie}
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
      ${movie ? html`<${FeatureBanner} movie=${movie} eyebrow="Surprise pick" />` : null}
      ${loading ? html`<${LoadingBlock} label="Pulling a high-quality random pick..." />` : null}
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
  onSelectMovie,
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
              <div className="poster-rail">
                ${results.recommendations.map(
                  (movie, index) => html`
                    <${PosterTile}
                      movie=${movie}
                      label=${`For You ${index + 1}`}
                      onSelect=${onSelectMovie}
                    />
                  `
                )}
              </div>
            `
          : null}
    </section>
  `;
}

function LetterboxdSection({
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
          <h2>Bring in Letterboxd exports through the reliable path</h2>
        </div>
        <p className="panel__copy">
          CSV upload is the supported import path here. Public username scraping is intentionally disabled
          because Letterboxd has no official public API and the HTML surface is fragile.
        </p>
      </div>

      <div className="form-grid">
        <div className="letterboxd-note">
          <span>Username import unavailable</span>
          <p>Use a CSV export from Letterboxd ratings, diary, or watch history instead.</p>
        </div>
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
                <p>Imported titles: ${formatImportedTitles(result.imported_titles)}</p>
              </div>
              <div className="poster-rail">
                ${result.recommendations.map(
                  (movie, index) => html`
                    <${PosterTile}
                      movie=${movie}
                      label=${`LBXD ${index + 1}`}
                    />
                  `
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
  const [streamingProviders, setStreamingProviders] = useState(null);

  const [filters, setFilters] = useState(emptyFilters);

  const [query, setQuery] = useState("Interstellar");
  const [debouncedQuery, setDebouncedQuery] = useState("Interstellar");
  const [searchResults, setSearchResults] = useState([]);
  const [searchLoading, setSearchLoading] = useState(false);
  const [searchError, setSearchError] = useState("");

  const [selectedMovie, setSelectedMovie] = useState(null);
  const [seedMovie, setSeedMovie] = useState(null);
  const [similarMethod, setSimilarMethod] = useState("cosine");
  const [similarResults, setSimilarResults] = useState([]);
  const [similarLoading, setSimilarLoading] = useState(false);
  const [similarError, setSimilarError] = useState("");

  const [randomMovie, setRandomMovie] = useState(null);
  const [randomLoading, setRandomLoading] = useState(false);
  const [randomError, setRandomError] = useState("");

  const [favoriteTitles, setFavoriteTitles] = useState("Arrival, Her, Moonlight");
  const [ratedMoviesText, setRatedMoviesText] = useState("Arrival | 5\nMoonlight | 5\nHer | 4.5");
  const [personalizedLoading, setPersonalizedLoading] = useState(false);
  const [personalizedError, setPersonalizedError] = useState("");
  const [personalizedResults, setPersonalizedResults] = useState(null);

  const [letterboxdCsvText, setLetterboxdCsvText] = useState("");
  const [letterboxdFile, setLetterboxdFile] = useState(null);
  const [letterboxdLoading, setLetterboxdLoading] = useState(false);
  const [letterboxdError, setLetterboxdError] = useState("");
  const [letterboxdResult, setLetterboxdResult] = useState(null);

  useEffect(() => {
    const timeoutId = window.setTimeout(() => {
      setDebouncedQuery(query);
    }, 300);

    return () => window.clearTimeout(timeoutId);
  }, [query]);

  useEffect(() => {
    async function loadHealth() {
      try {
        const payload = await getHealth();
        setHealth(payload);
      } catch (error) {
        setAppError(error.message);
        return;
      }

      try {
        const providerPayload = await getStreamingProviders();
        setStreamingProviders(providerPayload);
      } catch (error) {
        setStreamingProviders({ enabled: false, providers: [], watch_region: "US", message: error.message });
      }
    }

    loadHealth();
  }, []);

  useEffect(() => {
    async function runSearch() {
      if (!debouncedQuery.trim()) {
        startTransition(() => {
          setSearchResults([]);
          setSelectedMovie(null);
          setSeedMovie(null);
          setSimilarResults([]);
          setSimilarError("");
        });
        return;
      }

      try {
        setSearchLoading(true);
        setSearchError("");
        setSimilarError("");
        const filterPayload = toApiFilters(filters);
        const payload = await searchMovies({
          q: debouncedQuery,
          limit: 8,
          ...filterPayload,
        });
        startTransition(() => {
          setSearchResults(payload.results);
          if (payload.results.length) {
            setSelectedMovie(payload.results[0]);
          } else {
            setSelectedMovie(null);
            setSeedMovie(null);
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
  }, [debouncedQuery, filters.genre, filters.decade, filters.minRating, filters.runtimeMax, filters.streamingServices]);

  useEffect(() => {
    async function runSimilar() {
      if (!selectedMovie?.movie_id) return;
      try {
        setSimilarLoading(true);
        setSimilarError("");
        const filterPayload = toApiFilters(filters);
        const payload = await getSimilarMovies({
          movie_id: selectedMovie.movie_id,
          method: similarMethod,
          top_n: 6,
          ...filterPayload,
        });
        startTransition(() => {
          setSeedMovie(payload.seed_movie);
          setSimilarResults(payload.recommendations);
        });
      } catch (error) {
        setSimilarError(error.message);
      } finally {
        setSimilarLoading(false);
      }
    }

    runSimilar();
  }, [selectedMovie, similarMethod, filters.genre, filters.decade, filters.minRating, filters.runtimeMax, filters.streamingServices]);

  useEffect(() => {
    refreshRandomMovie();
  }, [filters.genre, filters.decade, filters.minRating, filters.runtimeMax, filters.streamingServices]);

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

  const heroBackdrop = randomMovie?.backdrop_url || "";

  return html`
    <div className="page-shell">
      <header
        className="hero"
        style=${heroBackdrop
          ? {
              backgroundImage: `linear-gradient(90deg, rgba(6, 7, 10, 0.94), rgba(6, 7, 10, 0.54) 40%, rgba(6, 7, 10, 0.92)), url(${heroBackdrop})`,
            }
          : undefined}
      >
        <div className="hero__copy">
          <p className="hero__eyebrow">CineMatch ML</p>
          <h1>Your own movie shelf, tuned by metadata and taste.</h1>
          <p className="hero__lede">
            A darker, streaming-style interface over real recommendation logic: TF-IDF metadata vectors,
            cosine similarity, nearest neighbors, and personalization from favorites or Letterboxd exports.
          </p>
          <div className="hero__chips">
            <span>Real TMDb + MovieLens data</span>
            <span>Cosine similarity + k-NN</span>
            <span>Streaming-service filters</span>
            <span>Letterboxd CSV personalization</span>
          </div>
        </div>

        <div className="hero__stats">
          <div className="stat-card">
            <span>Catalog</span>
            <strong>${health?.movie_count || "..."}</strong>
          </div>
          <div className="stat-card">
            <span>Mode</span>
            <strong>${health?.demo_mode ? "Offline demo" : "Deploy shelf"}</strong>
          </div>
          <div className="stat-card">
            <span>Region</span>
            <strong>${streamingProviders?.watch_region || health?.watch_region || "US"} streaming</strong>
          </div>
        </div>
      </header>

      <${InlineError} message=${appError} />
      <${FilterBar}
        health=${health}
        filters=${filters}
        onChange=${updateFilter}
        streamingProviders=${streamingProviders}
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
            seedMovie=${seedMovie}
            similarMethod=${similarMethod}
            setSimilarMethod=${setSimilarMethod}
            similarLoading=${similarLoading}
            similarError=${similarError}
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
            onSelectMovie=${setSelectedMovie}
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
