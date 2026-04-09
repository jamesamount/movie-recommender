# Data Layout

This project is designed to use real-world movie metadata and ratings. It supports two modes:

1. Full dataset mode
Place real datasets into these folders:

- `data/raw/tmdb/movies_metadata.csv`
- `data/raw/tmdb/credits.csv`
- `data/raw/tmdb/keywords.csv`
- `data/raw/tmdb/links_small.csv` or `data/raw/movielens/links.csv`
- `data/raw/tmdb/ratings_small.csv` or `data/raw/movielens/ratings.csv`

Recommended sources:

- Kaggle "The Movies Dataset" for TMDb metadata exports
- MovieLens `ml-latest-small` or larger for user rating signals

2. Offline demo mode
If the raw files above are missing, the pipeline falls back to `data/demo/demo_movies.csv`.

Important note:
`data/demo/demo_movies.csv` is a compact hand-curated subset of real movies used only for local smoke testing when the large raw datasets are not present. The actual portfolio story for this project is the real TMDb + MovieLens ingestion path implemented in `ml/data_loader.py`.

The build step writes:

- `data/processed/catalog_preview.csv`
- `models/artifacts/movie_recommender.joblib`

