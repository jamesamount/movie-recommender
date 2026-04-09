from __future__ import annotations

from ml.data_loader import load_movie_catalog
from ml.feature_engineering import build_artifact, save_artifact


def main() -> None:
    dataset = load_movie_catalog()
    result = build_artifact(dataset.catalog, dataset.source_name)
    save_artifact(result)
    print(
        f"Built recommender artifact for {len(dataset.catalog)} movies "
        f"using '{dataset.source_name}'. Demo mode: {dataset.used_demo_data}"
    )


if __name__ == "__main__":
    main()

