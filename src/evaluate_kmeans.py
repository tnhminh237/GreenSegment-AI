
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score, davies_bouldin_score

# ======================================
# 1. CONFIG
# ======================================

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "processed"
OUT_DIR = ROOT / "reports" / "model_evaluation"
OUT_DIR.mkdir(parents=True, exist_ok=True)

TRAIN_PATH = DATA_DIR / "greensegment_train_2024.csv"
TEST_PATH = DATA_DIR / "greensegment_test_2024.csv"

FEATURE_COLS = [
    "share_agriculture_2024",
    "share_energy_2024",
    "share_industry_2024",
    "share_international_2024",
    "share_residential_2024",
    "share_transport_2024",
    "share_waste_2024"
]

K = 3
RANDOM_STATE = 42
N_INIT = 20
SAMPLE_SIZE = 2000


# ======================================
# 2. LOAD & VALIDATE DATA
# ======================================

def load_data(path):
    df = pd.read_csv(path, encoding="utf-8-sig")

    if df["city_id"].isna().any():
        raise ValueError("Missing city_id")

    if df["city_id"].duplicated().any():
        raise ValueError("Duplicate city_id")

    X = df[FEATURE_COLS].to_numpy(dtype=float)

    if not np.isfinite(X).all():
        raise ValueError("NaN or Inf detected")

    if ((X < 0) | (X > 1)).any():
        raise ValueError("Invalid emission shares")

    if not np.allclose(X.sum(axis=1), 1.0, atol=1e-6):
        raise ValueError("Shares do not sum to 1")

    return df, X


# ======================================
# 3. EVALUATION
# ======================================

def evaluate(name, X, labels, model):
    counts = np.bincount(labels, minlength=K)

    if (counts == 0).any():
        raise ValueError(f"{name}: Empty cluster detected")

    silhouette = silhouette_score(
        X,
        labels,
        sample_size=min(SAMPLE_SIZE, len(X)),
        random_state=RANDOM_STATE
    )

    dbi = davies_bouldin_score(X, labels)

    distances = model.transform(X)
    mean_squared_distance = np.mean(
        np.min(distances ** 2, axis=1)
    )

    return {
        "split": name,
        "n_cities": len(X),
        "k": K,
        "silhouette_sample": silhouette,
        "davies_bouldin": dbi,
        "mean_squared_distance_to_centroid": mean_squared_distance,
        "min_cluster_size": counts.min(),
        "max_cluster_size": counts.max()
    }


# ======================================
# 4. MAIN
# ======================================

def main():

    train_df, X_train = load_data(TRAIN_PATH)
    test_df, X_test = load_data(TEST_PATH)

    if not set(train_df["city_id"]).isdisjoint(
        set(test_df["city_id"])
    ):
        raise ValueError("Train/Test ID overlap")

    model = KMeans(
        n_clusters=K,
        random_state=RANDOM_STATE,
        n_init=N_INIT
    )

    train_labels = model.fit_predict(X_train)
    test_labels = model.predict(X_test)

    results = pd.DataFrame([
        evaluate("Train", X_train, train_labels, model),
        evaluate("Test", X_test, test_labels, model)
    ])

    # Output 1: CSV
    results.to_csv(
        OUT_DIR / "kmeans_train_test_evaluation.csv",
        index=False,
        encoding="utf-8-sig"
    )

    # Output 2: PNG
    fig, axes = plt.subplots(1, 2, figsize=(10, 4))

    axes[0].bar(
        results["split"],
        results["silhouette_sample"]
    )
    axes[0].set_title("Silhouette Score")
    axes[0].set_ylabel("Higher is better")

    axes[1].bar(
        results["split"],
        results["davies_bouldin"]
    )
    axes[1].set_title("Davies-Bouldin Index")
    axes[1].set_ylabel("Lower is better")

    plt.tight_layout()

    plt.savefig(
        OUT_DIR / "kmeans_train_test_comparison.png",
        dpi=300,
        bbox_inches="tight"
    )
    plt.close()

    print("\nTRAIN / TEST EVALUATION")
    print(results.round(4).to_string(index=False))
    print("\nCompleted! Only 2 output files generated.")


if __name__ == "__main__":
    main()
