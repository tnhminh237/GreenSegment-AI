
from pathlib import Path

import numpy as np
import pandas as pd
import matplotlib.pyplot as plt

from sklearn.cluster import KMeans
from sklearn.metrics import (
    silhouette_score,
    davies_bouldin_score
)

# ==========================================
# 1. CONFIG
# ==========================================

ROOT = Path(__file__).resolve().parent.parent

TRAIN_PATH = (
    ROOT / "data" / "processed"
    / "greensegment_train_2024.csv"
)

OUTPUT_DIR = ROOT / "reports" / "model_evaluation"
OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

RANDOM_STATE = 42
K_VALUES = range(2, 11)

FEATURE_COLS = [
    "share_agriculture_2024",
    "share_energy_2024",
    "share_industry_2024",
    "share_international_2024",
    "share_residential_2024",
    "share_transport_2024",
    "share_waste_2024"
]

# ==========================================
# 2. LOAD TRAIN DATA
# ==========================================

train_df = pd.read_csv(
    TRAIN_PATH,
    encoding="utf-8-sig"
)

X_train = train_df[FEATURE_COLS].to_numpy(
    dtype=float
)

if not np.isfinite(X_train).all():
    raise ValueError("Train contains NaN or Inf.")

if (X_train < 0).any() or (X_train > 1).any():
    raise ValueError("Invalid emission shares.")

if not np.allclose(
    X_train.sum(axis=1), 1.0, atol=1e-6
):
    raise ValueError("Shares do not sum to 1.")

print("Train shape:", X_train.shape)

# ==========================================
# 3. K-MEANS EXPERIMENTS
# ==========================================

results = []

for k in K_VALUES:

    model = KMeans(
        n_clusters=k,
        random_state=RANDOM_STATE,
        n_init=20,
        max_iter=300
    )

    labels = model.fit_predict(X_train)

    inertia = model.inertia_

    # Đánh giá trên mẫu cố định 2500 đô thị
    # để giảm chi phí tính Silhouette
    silhouette = silhouette_score(
        X_train,
        labels,
        sample_size=min(2500, len(X_train)),
        random_state=RANDOM_STATE
    )

    dbi = davies_bouldin_score(
        X_train,
        labels
    )

    sizes = np.bincount(labels, minlength=k)

    results.append({
        "k": k,
        "inertia": inertia,
        "silhouette": silhouette,
        "davies_bouldin": dbi,
        "min_cluster_size": sizes.min(),
        "max_cluster_size": sizes.max()
    })

    print(
        f"K={k} | "
        f"Inertia={inertia:.2f} | "
        f"Silhouette={silhouette:.4f} | "
        f"DBI={dbi:.4f}"
    )

# ==========================================
# 4. SAVE EVALUATION RESULTS
# ==========================================

results_df = pd.DataFrame(results)

results_df.to_csv(
    OUTPUT_DIR / "kmeans_evaluation.csv",
    index=False,
    encoding="utf-8-sig"
)

# ==========================================
# 5. GENERATE CHARTS
# ==========================================

def save_plot(column, title, ylabel, filename):

    plt.figure(figsize=(9, 5))

    plt.plot(
        results_df["k"],
        results_df[column],
        marker="o",
        linewidth=2
    )

    plt.xlabel("Number of Clusters (K)")
    plt.ylabel(ylabel)
    plt.title(title)
    plt.xticks(list(K_VALUES))
    plt.grid(alpha=0.3)
    plt.tight_layout()

    plt.savefig(
        OUTPUT_DIR / filename,
        dpi=300,
        bbox_inches="tight"
    )

    plt.close()


save_plot(
    "inertia",
    "Elbow Method - KMeans",
    "Inertia (WCSS)",
    "elbow.png"
)

save_plot(
    "silhouette",
    "Silhouette Score - KMeans",
    "Silhouette Score",
    "silhouette.png"
)

save_plot(
    "davies_bouldin",
    "Davies-Bouldin Index - KMeans",
    "Davies-Bouldin Index",
    "davies_bouldin.png"
)

# ==========================================
# 6. SUMMARY
# ==========================================

best_silhouette = results_df.loc[
    results_df["silhouette"].idxmax()
]

best_dbi = results_df.loc[
    results_df["davies_bouldin"].idxmin()
]

print("\nEXPERIMENT COMPLETED")
print("-" * 40)

print(
    "Best K by Silhouette:",
    int(best_silhouette["k"])
)

print(
    "Best K by DBI:",
    int(best_dbi["k"])
)

print("\nResults saved to:")
print(OUTPUT_DIR)

print(
    "\nReview Elbow, Silhouette and DBI "
    "before selecting the final K."
)
