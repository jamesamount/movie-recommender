const API_BASE = window.MOVIE_API_BASE || "http://localhost:8000";

function buildQuery(params) {
  const search = new URLSearchParams();
  Object.entries(params || {}).forEach(([key, value]) => {
    if (value !== undefined && value !== null && value !== "") {
      search.set(key, String(value));
    }
  });
  return search.toString();
}

async function request(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, options);
  const contentType = response.headers.get("content-type") || "";
  const payload = contentType.includes("application/json")
    ? await response.json()
    : await response.text();

  if (!response.ok) {
    const message =
      typeof payload === "object" && payload && "detail" in payload
        ? payload.detail
        : `Request failed with status ${response.status}`;
    throw new Error(message);
  }

  return payload;
}

export function getHealth() {
  return request("/health");
}

export function searchMovies(params) {
  return request(`/search?${buildQuery(params)}`);
}

export function getSimilarMovies(params) {
  return request(`/recommend/similar?${buildQuery(params)}`);
}

export function getRandomMovie(params) {
  return request(`/recommend/random?${buildQuery(params)}`);
}

export function getPersonalizedRecommendations(payload) {
  return request("/recommend/personalized", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
}

export function importLetterboxd(formData) {
  return request("/letterboxd/import", {
    method: "POST",
    body: formData,
  });
}

