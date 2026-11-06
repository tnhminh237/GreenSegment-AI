"""GreenSegment AI | Compare K-Means, GMM, and Ward on TRAIN data only.

Metrics: Silhouette (higher), Davies-Bouldin (lower), resampling ARI (higher).
Output: 4 PNG charts in reports/model_comparison/. No models or CSV are saved.
Run at project root: python src/compare_models.py
"""

from pathlib import Path
import warnings

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy.cluster.hierarchy import cut_tree, linkage
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.exceptions import ConvergenceWarning
from sklearn.metrics import (
    adjusted_rand_score,
    davies_bouldin_score,
    silhouette_score,
)
from sklearn.mixture import GaussianMixture

# ============================================================
# 1. CONFIGURATION
# ============================================================
ROOT = Path(__file__).resolve().parent.parent
TRAIN_FILE = ROOT / "data" / "processed" / "greensegment_train_2024.csv"
OUT_DIR = ROOT / "reports" / "model_comparison"
OUT_DIR.mkdir(parents=True, exist_ok=True)

FEATURE_COLS = [
    "share_agriculture_2024",
    "share_energy_2024",
    "share_industry_2024",
    "share_international_2024",
    "share_residential_2024",
    "share_transport_2024",
    "share_waste_2024",
]

K_VALUES = list(range(2, 11))  # Change to [3] to compare only K=3.
SEED = 42
SILHOUETTE_SAMPLE = 2000
STABILITY_REFERENCE_SIZE = 2500
STABILITY_SAMPLE_FRACTION = 0.80
STABILITY_REPEATS = 5
MODEL_NAMES = ("K-Means", "GMM", "Ward")

# ============================================================
# 2. LOAD AND CHECK THE TRAINING FEATURES
# ============================================================
def load_features():
    df = pd.read_csv(TRAIN_FILE, encoding="utf-8-sig")
    missing = sorted(set(FEATURE_COLS) - set(df.columns))
    if missing:
        raise ValueError(f"Missing feature columns: {missing}")
    if "city_id" in df.columns and df["city_id"].duplicated().any():
        raise ValueError("Duplicated city_id in training data")

    shares = df[FEATURE_COLS].to_numpy(dtype=float)
    if not np.isfinite(shares).all():
        raise ValueError("Shares contain missing or non-finite values")
    if (shares < -1e-10).any() or (shares > 1 + 1e-10).any():
        raise ValueError("Shares must be in [0, 1]")
    if not np.allclose(shares.sum(axis=1), 1.0, atol=1e-6):
        raise ValueError("Seven shares must sum to 1 for every city")

    # Seven shares sum to one, so only six dimensions are independent.
    # Orthogonal PCA -> 6 dimensions preserves Euclidean distances
    # on the compositional simplex (up to floating-point error).
    # Fit ONLY on Train; apply the SAME transform to all 3 models.
    x = PCA(n_components=6, svd_solver="full").fit_transform(shares)
    return x


# ============================================================
# 3. MODEL FITTING
# ============================================================
def fit_labels(name, x, k):
    if name == "K-Means":
        return KMeans(
            n_clusters=k, n_init=20, random_state=SEED, max_iter=300
        ).fit_predict(x)

    if name == "GMM":
        # PCA(6) removes the exact linear dependency of the 7 shares.
        # Regularization prevents poorly conditioned covariance matrices.
        with warnings.catch_warnings():
            warnings.simplefilter("once", ConvergenceWarning)
            return GaussianMixture(
                n_components=k,
                covariance_type="full",
                reg_covar=1e-5,
                n_init=3,
                max_iter=300,
                random_state=SEED,
            ).fit_predict(x)

    raise ValueError(f"Unknown model: {name}")


def all_ward_labels(x):
    # Compute the Ward hierarchy only ONCE for all K values.
    z = linkage(x, method="ward", metric="euclidean")
    return cut_tree(z, n_clusters=K_VALUES)


# ============================================================
# 4. EVALUATE SILHOUETTE AND DBI ON ALL TRAINING CITIES
# ============================================================
def evaluate_main(x):
    n = len(x)
    if n <= max(K_VALUES):
        raise ValueError("Not enough training rows for chosen K values")

    # Same evaluation sample for every model and K.
    rng = np.random.default_rng(SEED)
    idx = np.sort(rng.choice(n, size=min(SILHOUETTE_SAMPLE, n), replace=False))
    ward_matrix = all_ward_labels(x)
    scores = []

    for j, k in enumerate(K_VALUES):
        for name in MODEL_NAMES:
            labels = ward_matrix[:, j] if name == "Ward" else fit_labels(name, x, k)
            unique = np.unique(labels)
            if len(unique) < 2 or len(unique) >= len(x):
                sil, dbi = np.nan, np.nan
            else:
                labels_sample = labels[idx]
                sil = (
                    silhouette_score(x[idx], labels_sample)
                    if 2 <= len(np.unique(labels_sample)) < len(idx)
                    else np.nan
                )
                dbi = davies_bouldin_score(x, labels)

            scores.append({
                "model": name, "k": k,
                "silhouette": float(sil),
                "dbi": float(dbi),
                "actual_clusters": len(unique),
            })
            print(f"{name:7s} | K={k:2d} | Silhouette={sil:.4f} | DBI={dbi:.4f}")

    return pd.DataFrame(scores)


# ============================================================
# 5. STABILITY: ARI ON THE SAME POINTS AFTER RESAMPLING
# ============================================================
def evaluate_stability(x):
    """ARI vs. reference clustering on overlapping 80% samples.

    Every algorithm gets exactly the same reference points and subsamples.
    Ward is re-fitted on a subset, rather than using a nonexistent predict().
    ARI is computed only for point IDs present in both partitions.
    """
    rng = np.random.default_rng(SEED + 1)
    n_ref = min(STABILITY_REFERENCE_SIZE, len(x))
    ref_idx = np.sort(rng.choice(len(x), size=n_ref, replace=False))
    x_ref = x[ref_idx]
    sub_size = max(max(K_VALUES) + 1, int(n_ref * STABILITY_SAMPLE_FRACTION))
    sub_size = min(sub_size, n_ref - 1)
    subsets = [
        np.sort(rng.choice(n_ref, size=sub_size, replace=False))
        for _ in range(STABILITY_REPEATS)
    ]

    # Cache Ward clusterings: avoid recomputing the hierarchy for each K.
    ward_ref = all_ward_labels(x_ref)
    ward_subsets = [all_ward_labels(x_ref[idx]) for idx in subsets]

    stability = []
    for j, k in enumerate(K_VALUES):
        for name in MODEL_NAMES:
            base_labels = (
                ward_ref[:, j] if name == "Ward" else fit_labels(name, x_ref, k)
            )
            ari_values = []
            for run, idx in enumerate(subsets):
                new_labels = (
                    ward_subsets[run][:, j]
                    if name == "Ward" else fit_labels(name, x_ref[idx], k)
                )
                ari_values.append(adjusted_rand_score(base_labels[idx], new_labels))

            mean_ari = float(np.mean(ari_values))
            stability.append({
                "model": name, "k": k,
                "ari_mean": mean_ari,
                "ari_std": float(np.std(ari_values, ddof=1)) if len(ari_values) > 1 else 0.0,
            })
            print(f"{name:7s} | K={k:2d} | Stability ARI={mean_ari:.4f}")

    return pd.DataFrame(stability)


# ============================================================
# 6. SAVE ONLY PNG CHARTS (NO CSV / NO MODEL FILES)
# ============================================================
def draw_metric(ax, result, column, title, ylabel):
    for name in MODEL_NAMES:
        subset = result.loc[result["model"] == name].sort_values("k")
        ax.plot(subset["k"], subset[column], marker="o", label=name)
    ax.set_title(title)
    ax.set_xlabel("Number of clusters (K)")
    ax.set_ylabel(ylabel)
    ax.set_xticks(K_VALUES)
    ax.grid(alpha=0.25)
    ax.legend()


def save_plots(result):
    settings = [
        ("silhouette", "Silhouette Score", "Higher is better", "silhouette_comparison.png"),
        ("dbi", "Davies-Bouldin Index", "Lower is better", "dbi_comparison.png"),
        ("ari_mean", "Stability - Adjusted Rand Index", "Higher is better", "ari_comparison.png"),
    ]
    for column, title, direction, filename in settings:
        fig, ax = plt.subplots(figsize=(9, 5))
        draw_metric(ax, result, column, title, direction)
        fig.tight_layout()
        fig.savefig(OUT_DIR / filename, dpi=250, bbox_inches="tight")
        plt.close(fig)

    fig, axes = plt.subplots(1, 3, figsize=(18, 5))
    for ax, (column, title, direction, _) in zip(axes, settings):
        draw_metric(ax, result, column, title, direction)
    fig.suptitle("GreenSegment AI - Model Comparison (TRAIN only)", fontsize=14)
    fig.tight_layout()
    fig.savefig(OUT_DIR / "model_comparison.png", dpi=250, bbox_inches="tight")
    plt.close(fig)


def main():
    x = load_features()
    print(f"TRAIN: {len(x):,} cities | features: 7 shares -> PCA(6)")
    print("Testing K-Means, GMM(full), Ward...\n")

    main_scores = evaluate_main(x)
    print("\nChecking subsample stability using ARI...\n")
    stability_scores = evaluate_stability(x)
    results = main_scores.merge(stability_scores, on=["model", "k"], validate="one_to_one")
    save_plots(results)

    print("\nSUMMARY - candidates by criterion (TRAIN only):")
    for name, column, better in [
        ("Silhouette", "silhouette", "max"),
        ("DBI", "dbi", "min"),
        ("ARI", "ari_mean", "max"),
    ]:
        valid = results.dropna(subset=[column])
        row = valid.loc[valid[column].idxmax() if better == "max" else valid[column].idxmin()]
        print(f"  {name:10s}: {row['model']} K={int(row['k'])}, score={row[column]:.4f}")

    print("\nCharts saved to:", OUT_DIR)
    print("  silhouette_comparison.png")
    print("  dbi_comparison.png")
    print("  ari_comparison.png")
    print("  model_comparison.png")
    print("No models or CSV files were written. TEST data was not used.")
    print("Choose a model using all three metrics and cluster interpretability, then evaluate on TEST.")


if __name__ == "__main__":
    main()
