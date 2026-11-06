"""GreenSegment AI — stability of K-Means (K=3) on TRAIN only.

Place at: GreenSegment AI/src/check_kmeans_stability.py
Run: python src/check_kmeans_stability.py

Repeatedly fit K-Means on 80% subsets of TRAIN, then assign the same
full TRAIN reference points. ARI compares these assignments.
"""
from pathlib import Path
from itertools import combinations
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import adjusted_rand_score

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "processed" / "greensegment_train_2024.csv"
OUT = ROOT / "reports" / "model_evaluation"
OUT.mkdir(parents=True, exist_ok=True)

FEATURE_COLS = [
    "share_agriculture_2024", "share_energy_2024",
    "share_industry_2024", "share_international_2024",
    "share_residential_2024", "share_transport_2024",
    "share_waste_2024",
]
K = 3
N_RUNS = 20
SUBSAMPLE_FRACTION = 0.80
RANDOM_STATE = 42


def main():
    df = pd.read_csv(DATA, encoding="utf-8-sig")
    if df["city_id"].duplicated().any():
        raise ValueError("Train data contains duplicate city_id")
    x = df[FEATURE_COLS].to_numpy(dtype=float)
    if not np.isfinite(x).all() or (x < 0).any() or (x > 1).any():
        raise ValueError("Invalid share values")
    if not np.allclose(x.sum(axis=1), 1, atol=1e-6):
        raise ValueError("Each city's 7 shares must sum to 1")

    # Reference clustering on complete TRAIN data, not on TEST.
    baseline = KMeans(n_clusters=K, n_init=20, random_state=RANDOM_STATE)
    reference_labels = baseline.fit_predict(x)

    rng = np.random.default_rng(RANDOM_STATE)
    n_sample = int(round(len(x) * SUBSAMPLE_FRACTION))
    predictions = []
    rows = []

    for run in range(1, N_RUNS + 1):
        sampled_indices = rng.choice(len(x), size=n_sample, replace=False)
        model = KMeans(n_clusters=K, n_init=20, random_state=RANDOM_STATE + run)
        model.fit(x[sampled_indices])

        # Every run is evaluated on the SAME points so ARI is comparable.
        labels_all_train = model.predict(x)
        predictions.append(labels_all_train)
        counts = np.bincount(labels_all_train, minlength=K)
        ari = adjusted_rand_score(reference_labels, labels_all_train)
        rows.append({
            "run": run,
            "subsample_rows": n_sample,
            "ari_vs_full_train_baseline": ari,
            "min_cluster_size_on_full_train": int(counts.min()),
            "max_cluster_size_on_full_train": int(counts.max()),
        })
        print(f"Run {run:02d}/{N_RUNS}: ARI vs baseline = {ari:.4f}")

    per_run = pd.DataFrame(rows)
    per_run.to_csv(OUT / "kmeans_stability_runs.csv", index=False, encoding="utf-8-sig")

    pairwise_ari = [
        adjusted_rand_score(predictions[i], predictions[j])
        for i, j in combinations(range(N_RUNS), 2)
    ]
    summary = pd.DataFrame([
        {
            "comparison": "vs_full_train_baseline",
            "n_comparisons": N_RUNS,
            "mean_ari": float(per_run["ari_vs_full_train_baseline"].mean()),
            "std_ari": float(per_run["ari_vs_full_train_baseline"].std(ddof=0)),
            "min_ari": float(per_run["ari_vs_full_train_baseline"].min()),
            "max_ari": float(per_run["ari_vs_full_train_baseline"].max()),
        },
        {
            "comparison": "pairwise_subsample_models",
            "n_comparisons": len(pairwise_ari),
            "mean_ari": float(np.mean(pairwise_ari)),
            "std_ari": float(np.std(pairwise_ari)),
            "min_ari": float(np.min(pairwise_ari)),
            "max_ari": float(np.max(pairwise_ari)),
        },
    ])
    summary.to_csv(OUT / "kmeans_stability_summary.csv", index=False, encoding="utf-8-sig")

    print("\nSTABILITY CHECK COMPLETED")
    print(summary.to_string(index=False, float_format=lambda v: f"{v:.4f}"))
    print(f"\nSaved to: {OUT}")
    print("NOTE: ARI measures agreement between clusterings, not prediction accuracy.")


if __name__ == "__main__":
    main()
