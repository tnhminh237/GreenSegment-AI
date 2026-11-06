"""GreenSegment AI | Huấn luyện K-Means chính thức trên toàn bộ dữ liệu.

Đặt file tại: GreenSegment AI/src/finalize_kmeans.py
Đầu vào: data/processed/greensegment_features_2024.csv
Chạy từ thư mục gốc dự án: python src/finalize_kmeans.py

Lưu ý: K=3 đã được chọn qua thử nghiệm trên tập Train và đánh giá Test.
Không dùng kết quả ở đây để lựa chọn lại K hoặc đánh giá tổng quát hóa.
"""

from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import davies_bouldin_score, silhouette_score

ROOT = Path(__file__).resolve().parent.parent
INPUT_FILE = ROOT / "data" / "processed" / "greensegment_features_2024.csv"
DATA_OUTPUT = ROOT / "data" / "processed" / "greensegment_clusters_2024.csv"
MODEL_DIR = ROOT / "models"
ANALYSIS_DIR = ROOT / "reports" / "cluster_analysis"
EVALUATION_DIR = ROOT / "reports" / "model_evaluation"

K = 3
RANDOM_STATE = 42
N_INIT = 20

SECTORS = [
    "agriculture", "energy", "industry", "international",
    "residential", "transport", "waste",
]
FEATURE_COLS = [f"share_{sector}_2024" for sector in SECTORS]


def main() -> None:
    if not INPUT_FILE.is_file():
        raise FileNotFoundError(f"Không tìm thấy file đầu vào: {INPUT_FILE}")

    df = pd.read_csv(INPUT_FILE, encoding="utf-8-sig")
    required = ["city_id", "city_name", "country_name", *FEATURE_COLS]
    missing = [column for column in required if column not in df.columns]
    if missing:
        raise ValueError(f"File chưa đủ cột cần thiết: {missing}")
    if df["city_id"].isna().any() or df["city_id"].duplicated().any():
        raise ValueError("city_id bị thiếu hoặc trùng lặp.")

    features = df[FEATURE_COLS].apply(pd.to_numeric, errors="raise")
    X = features.to_numpy(dtype=np.float64)
    if not np.isfinite(X).all():
        raise ValueError("Các tỷ trọng có NaN hoặc giá trị vô hạn.")
    if ((X < -1e-10) | (X > 1 + 1e-10)).any():
        raise ValueError("Các tỷ trọng không nằm trong khoảng [0, 1].")
    if not np.allclose(X.sum(axis=1), 1.0, atol=1e-6):
        raise ValueError("Tổng 7 tỷ trọng phải gần bằng 1 ở mỗi đô thị.")
    if len(df) < K:
        raise ValueError("Số đô thị ít hơn số cụm K.")

    print(f"Số đô thị: {len(df):,} | Đặc trưng K-Means: {X.shape[1]}")
    print(f"Huấn luyện K-Means: K={K}, random_state={RANDOM_STATE}, n_init={N_INIT}")

    model = KMeans(
        n_clusters=K,
        random_state=RANDOM_STATE,
        n_init=N_INIT,
        max_iter=300,
    )
    labels = model.fit_predict(X).astype(int)
    distances = model.transform(X)[np.arange(len(X)), labels]

    # Dữ liệu phục vụ bản đồ và phân tích: giữ nguyên 20 cột ban đầu.
    assigned = df.copy()
    assigned["cluster_id"] = labels
    assigned["distance_to_centroid"] = distances

    # Tâm cụm K-Means có cùng hệ quy chiếu với 7 tỷ trọng GHG (0..1).
    centers = pd.DataFrame(model.cluster_centers_, columns=FEATURE_COLS)
    centers.insert(0, "cluster_id", np.arange(K))
    counts = assigned.groupby("cluster_id").size().reindex(range(K), fill_value=0)
    centers.insert(1, "city_count", counts.to_numpy())
    centers.insert(2, "city_percentage", (100 * counts / len(df)).to_numpy())
    centers["dominant_sector"] = [
        SECTORS[int(np.argmax(center))] for center in model.cluster_centers_
    ]

    # Thống kê cơ bản; chưa đặt tên nhóm trước khi phân tích nội dung.
    sizes = pd.DataFrame({
        "cluster_id": np.arange(K),
        "city_count": counts.to_numpy(),
        "city_percentage": (100 * counts / len(df)).to_numpy(),
    })

    # Silhouette dùng mẫu cố định để không tốn quá nhiều RAM.
    sample_n = min(2500, len(X))
    sil = silhouette_score(X, labels, sample_size=sample_n, random_state=RANDOM_STATE)
    dbi = davies_bouldin_score(X, labels)
    metrics = pd.DataFrame([{
        "dataset": "all_cities_refit",
        "n_cities": len(X),
        "k": K,
        "inertia": float(model.inertia_),
        "silhouette_sample": float(sil),
        "silhouette_sample_size": sample_n,
        "davies_bouldin": float(dbi),
        "random_state": RANDOM_STATE,
        "n_init": N_INIT,
    }])

    for directory in (MODEL_DIR, ANALYSIS_DIR, EVALUATION_DIR, DATA_OUTPUT.parent):
        directory.mkdir(parents=True, exist_ok=True)

    joblib.dump(model, MODEL_DIR / "kmeans_model.joblib")
    metadata = {
        "algorithm": "KMeans",
        "k": K,
        "feature_columns_ordered": FEATURE_COLS,
        "training_rows": len(df),
        "random_state": RANDOM_STATE,
        "n_init": N_INIT,
        "feature_description": "Raw GHG sector shares (0-1); no scaling/PCA",
        "important_note": "Cluster IDs are arbitrary; name them after reviewing cluster profiles.",
    }
    (MODEL_DIR / "kmeans_metadata.json").write_text(
        json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    assigned.to_csv(DATA_OUTPUT, index=False, encoding="utf-8-sig")
    centers.to_csv(ANALYSIS_DIR / "cluster_centroids_2024.csv", index=False, encoding="utf-8-sig")
    sizes.to_csv(ANALYSIS_DIR / "cluster_sizes_2024.csv", index=False, encoding="utf-8-sig")
    metrics.to_csv(EVALUATION_DIR / "kmeans_final_metrics.csv", index=False, encoding="utf-8-sig")

    print("\nHOÀN THÀNH HUẤN LUYỆN CHÍNH THỨC")
    print(sizes.to_string(index=False, float_format=lambda x: f"{x:.2f}"))
    print(f"Silhouette (mẫu {sample_n}): {sil:.4f} | DBI: {dbi:.4f}")
    print("\nĐã xuất:")
    for path in [
        DATA_OUTPUT,
        MODEL_DIR / "kmeans_model.joblib",
        MODEL_DIR / "kmeans_metadata.json",
        ANALYSIS_DIR / "cluster_centroids_2024.csv",
        ANALYSIS_DIR / "cluster_sizes_2024.csv",
        EVALUATION_DIR / "kmeans_final_metrics.csv",
    ]:
        print(" -", path.relative_to(ROOT))
    print("\nTiếp theo: phân tích cơ cấu 7 ngành và đặt tên 3 cụm.")


if __name__ == "__main__":
    main()
