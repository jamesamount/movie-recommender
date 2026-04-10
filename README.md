# CineMatch ML

CineMatch ML is a polished full-stack movie recommendation engine built to showcase practical machine learning, retrieval, and personalization work in a portfolio setting. It combines real-world movie metadata with vector-based similarity, nearest-neighbor retrieval, random discovery, and user taste profiling from favorite movies or Letterboxd exports.

## What the app does

- Search for a movie and retrieve similar titles
- Rank related films with cosine similarity or k-nearest neighbors
- Explore a weighted random recommendation with sensible quality controls
- Build personalized recommendations from favorite movies or manually entered ratings
- Import Letterboxd CSV exports and exclude already watched or rated titles
- Filter recommendations by genre, decade, minimum rating, and runtime

## Tech stack

- `Python` for preprocessing and recommendation logic
- `pandas`, `NumPy`, `scikit-learn`, `SciPy`, `joblib`
- `FastAPI` for the backend API
- `React` on the frontend, served buildlessly through FastAPI for easy local setup

## Project structure

```text
.
├── backend/
│   └── app/
│       ├── main.py
│       ├── schemas.py
│       └── services/
├── data/
│   ├── demo/
│   ├── processed/
│   └── raw/
├── frontend/
│   ├── index.html
│   └── src/
├── ml/
│   ├── build_pipeline.py
│   ├── data_loader.py
│   ├── feature_engineering.py
│   └── recommender.py
├── models/
│   └── artifacts/
├── requirements.txt
└── README.md
```

## Dataset strategy

The recommendation pipeline is designed for real-world datasets:

- TMDb metadata exports from Kaggle's "The Movies Dataset"
- MovieLens ratings data for extra user-signal features

The loader looks for:

- `data/raw/tmdb/movies_metadata.csv`
- `data/raw/tmdb/credits.csv`
- `data/raw/tmdb/keywords.csv`
- `data/raw/tmdb/links_small.csv` or `data/raw/movielens/links.csv`
- `data/raw/tmdb/ratings_small.csv` or `data/raw/movielens/ratings.csv`

If those files are missing, the app falls back to `data/demo/demo_movies.csv`, a compact offline subset of real movies included only so the project runs immediately. The real portfolio path is the TMDb + MovieLens ingestion code in [`ml/data_loader.py`](/Users/mount/Documents/New%20project/ml/data_loader.py).

## Recommendation logic

### 1. Cleaning and merging

The pipeline:

- parses TMDb JSON-like fields for genres, keywords, cast, and crew
- extracts the director from crew metadata
- normalizes release year, popularity, runtime, and vote statistics
- optionally joins MovieLens ratings by TMDb ID through link files
- drops duplicate title-year combinations after sorting for stronger metadata coverage

### 2. Feature engineering

Each movie is turned into a combined representation using:

- overview text
- genres
- keywords
- top-billed cast
- director
- decade token
- numeric features such as year, TMDb vote average, vote count, popularity, runtime, and average user rating

Text features are vectorized with TF-IDF. Numeric features are scaled and appended to the sparse text matrix. The combined matrix is L2-normalized for stable cosine similarity and nearest-neighbor retrieval.

### 3. Similar recommendations

Two retrieval modes are exposed:

- cosine similarity across the feature matrix
- brute-force k-nearest neighbors with cosine distance

Results are re-ranked with a hybrid score:

- `78%` similarity
- `22%` quality prior based on weighted rating plus popularity

That quality prior prevents weak obscure titles from dominating purely lexical matches.

### 4. Personalization

The app creates a user taste profile by averaging the feature vectors from:

- manually entered favorites
- manually entered rated films
- imported Letterboxd CSV rows

Rated titles can be weighted by score, and already watched titles are excluded from the final recommendation set.

## Letterboxd approach

Letterboxd does not offer an unrestricted public API for this use case. This project handles that carefully:

- reliable path: CSV import from Letterboxd exports
- optional path: public username scraping is intentionally disabled by default

Why the limitation matters:

- scraping depends on brittle HTML
- layouts can change without notice
- automated access may raise legal or ethical questions if overused

The backend therefore fails gracefully and clearly recommends CSV import. This is documented both in the UI and in the API behavior.

## API endpoints

- `GET /health`
- `GET /search`
- `GET /recommend/similar`
- `GET /recommend/random`
- `POST /recommend/personalized`
- `POST /letterboxd/import`

## Running locally

### 1. Create an environment

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### 2. Add datasets

Either:

- place the TMDb + MovieLens files into `data/raw/...`

Or:

- do nothing and use the included demo catalog for local testing

### 3. Build the recommendation artifact

```bash
python3 -m ml.build_pipeline
```

This writes:

- `models/artifacts/movie_recommender.joblib`
- `data/processed/catalog_preview.csv`

For two different artifact styles:

- local full profile:

```bash
MOVIE_BUILD_PROFILE=full python3 -m ml.build_pipeline
```

- Render-friendly deploy profile:

```bash
MOVIE_BUILD_PROFILE=deploy MOVIE_DEPLOY_CATALOG_LIMIT=12000 python3 -m ml.build_pipeline
```

The deploy profile keeps the full local pipeline intact while producing a smaller artifact:

- fewer catalog rows
- smaller TF-IDF vocabulary
- `float32` feature matrix
- no persisted k-NN model in the artifact

### 4. Start the app

```bash
uvicorn backend.app.main:app --reload
```

Open [http://localhost:8000](http://localhost:8000).

### 5. After the build finishes

If the build succeeds, the next step is to run the app and verify it is using the expected dataset:

```bash
uvicorn backend.app.main:app --reload
```

Then open:

- `http://localhost:8000`
- `http://localhost:8000/health`

If `/health` shows `demo_mode: false`, the full dataset was picked up successfully.

## Deploying larger datasets

The app now supports environment-based storage overrides, which makes hosting easier when you want to move beyond the built-in demo catalog:

- `MOVIE_DATA_DIR`
- `MOVIE_RAW_TMDB_DIR`
- `MOVIE_RAW_MOVIELENS_DIR`
- `MOVIE_PROCESSED_DIR`
- `MOVIE_MODELS_DIR`
- `MOVIE_ARTIFACT_PATH`

This is useful if your host mounts a separate disk or storage directory and you want the app to read raw data and model artifacts from there instead of the repo checkout.

For Render free tier, the recommended workflow is:

1. Build the deploy artifact locally
2. Commit `models/artifacts/movie_recommender.joblib`
3. Use a Render build command that only installs dependencies

Example local build:

```bash
source .venv/bin/activate
MOVIE_BUILD_PROFILE=deploy MOVIE_DEPLOY_CATALOG_LIMIT=12000 python -m ml.build_pipeline
```

Recommended Render build command:

```bash
pip install -r requirements.txt
```

Recommended Render start command:

```bash
uvicorn backend.app.main:app --host 0.0.0.0 --port $PORT
```

## Streaming-service filters

The app now supports filtering recommendations by streaming services you already have, but this feature depends on TMDb watch-provider data at runtime.

Set one of these backend environment variables:

- `TMDB_API_READ_ACCESS_TOKEN`
- `TMDB_API_KEY`

Optional:

- `TMDB_WATCH_REGION=US`

Once configured, the UI can:

- list available providers
- let users select the services they have
- filter search, similar, random, personalized, and Letterboxd recommendation results
- attach "Where to watch" links when TMDb provides them
- recover missing backdrop images for featured movies at runtime when the dataset does not include them

## Example user flows

### Search and similar retrieval

1. Search for `Interstellar`
2. Click the result card
3. Compare cosine recommendations against k-NN recommendations

### Manual personalization

1. Enter favorites such as `Arrival, Her, Moonlight`
2. Add rated titles like:

```text
Arrival | 5
Her | 4.5
Moonlight | 5
```

3. Generate personalized recommendations

### Letterboxd import

1. Upload a ratings export CSV or paste CSV rows
2. The system parses the titles and ratings
3. A user taste profile is built
4. Already imported titles are excluded from final recommendations

There is a sample CSV at [`data/demo/sample_letterboxd_ratings.csv`](/Users/mount/Documents/New%20project/data/demo/sample_letterboxd_ratings.csv).

## Evaluation and validation ideas

This repository includes the main mechanics needed for a portfolio-ready evaluation section:

- compare cosine and k-NN outputs for the same seed movie
- inspect whether personalized outputs align with known favorites
- verify watched-title exclusion from Letterboxd imports
- inspect `data/processed/catalog_preview.csv` to confirm merged and cleaned features

Suggested next steps for a deeper portfolio write-up:

- add offline retrieval metrics against held-out user ratings
- benchmark demo mode versus full TMDb + MovieLens mode
- log recommendation clickthroughs for lightweight product evaluation

## Notes for reviewers

- The frontend is React, but intentionally buildless so it can run through FastAPI without a Node toolchain.
- The real preprocessing and recommendation logic lives in the Python pipeline, not the UI.
- Demo mode exists only to keep the repository runnable when large external datasets are not bundled.
