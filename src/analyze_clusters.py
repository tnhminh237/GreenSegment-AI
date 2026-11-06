"""GreenSegment AI | Cluster Analysis for the final K-Means (2024).

Place this file in: GreenSegment AI/src/analyze_clusters.py
Input:  data/processed/greensegment_clusters_2024.csv
Optional consistency check: reports/cluster_analysis/cluster_centroids_2024.csv
Outputs: reports/cluster_analysis/

Run from the project's root directory:
    python src/analyze_clusters.py

This script DOES NOT train a model or modify the input CSV.
"""

from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")  # Safe for VS Code terminals / headless execution
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd


ROOT = Path(__file__).resolve().parent.parent
INPUT_PATH = ROOT / "data" / "processed" / "greensegment_clusters_2024.csv"
OUTPUT_DIR = ROOT / "reports" / "cluster_analysis"
CENTROID_PATH = OUTPUT_DIR / "cluster_centroids_2024.csv"
TOP_N_CITIES = 5

SECTORS = [
    "agriculture", "energy", "industry", "international",
    "residential", "transport", "waste",
]
SECTOR_NAMES_VI = {
    "agriculture": "Nông nghiệp",
    "energy": "Năng lượng",
    "industry": "Công nghiệp",
    "international": "Quốc tế",
    "residential": "Dân cư",
    "transport": "Giao thông",
    "waste": "Chất thải",
}
SHARE_COLS = [f"share_{sector}_2024" for sector in SECTORS]
GHG_COLS = [f"ghg_{sector}_2024" for sector in SECTORS]
REQUIRED_COLS = [
    "city_id", "city_name", "country_name", "cluster_id",
    "distance_to_centroid", "ghg_total_2024", *SHARE_COLS, *GHG_COLS,
]


def load_and_validate() -> pd.DataFrame:
    if not INPUT_PATH.exists():
        raise FileNotFoundError(f"Không tìm thấy dữ liệu: {INPUT_PATH}")
    df = pd.read_csv(INPUT_PATH, encoding="utf-8-sig")
    missing = sorted(set(REQUIRED_COLS) - set(df.columns))
    if missing:
        raise ValueError(f"Thiếu các cột bắt buộc: {missing}")
    if df.empty or df["city_id"].isna().any() or df["city_id"].duplicated().any():
        raise ValueError("File rỗng hoặc city_id bị thiếu/trùng.")
    if df["cluster_id"].isna().any():
        raise ValueError("Có cluster_id bị thiếu.")

    numeric_cols = ["distance_to_centroid", "ghg_total_2024", *SHARE_COLS, *GHG_COLS]
    for col in numeric_cols:
        df[col] = pd.to_numeric(df[col], errors="raise")
    if not np.isfinite(df[numeric_cols].to_numpy(dtype=float)).all():
        raise ValueError("Có giá trị NaN/Inf trong cột số.")
    if (df["distance_to_centroid"] < 0).any():
        raise ValueError("Có khoảng cách đến tâm cụm âm.")
    if (df[GHG_COLS] < 0).any().any() or (df["ghg_total_2024"] <= 0).any():
        raise ValueError("Có giá trị GHG âm hoặc tổng GHG không dương.")
    shares = df[SHARE_COLS].to_numpy(dtype=float)
    if (shares < -1e-9).any() or (shares > 1 + 1e-9).any():
        raise ValueError("Có tỷ trọng phát thải ngoài khoảng [0, 1].")
    if not np.allclose(shares.sum(axis=1), 1.0, atol=1e-7):
        raise ValueError("Tổng 7 tỷ trọng không bằng 1 ở một số đô thị.")
    if not np.allclose(
        df[GHG_COLS].sum(axis=1).to_numpy(),
        df["ghg_total_2024"].to_numpy(),
        rtol=1e-7, atol=1e-5,
    ):
        raise ValueError("Tổng 7 ngành không khớp ghg_total_2024.")

    if not pd.api.types.is_integer_dtype(df["cluster_id"]):
        if not np.allclose(df["cluster_id"].to_numpy(),
                           np.rint(df["cluster_id"].to_numpy())):
            raise ValueError("cluster_id không phải các số nguyên.")
        df["cluster_id"] = df["cluster_id"].astype(int)
    if df["cluster_id"].nunique() < 2:
        raise ValueError("Phải có ít nhất hai cụm để phân tích.")

    # Optional: confirm the centroids exported from finalize_kmeans.py match.
    if CENTROID_PATH.is_file():
        centroids = pd.read_csv(CENTROID_PATH, encoding="utf-8-sig")
        if set(["cluster_id", "city_count", *SHARE_COLS]).issubset(centroids.columns):
            actual = df.groupby("cluster_id")[SHARE_COLS].mean()
            actual_n = df.groupby("cluster_id").size()
            centroids = centroids.set_index("cluster_id")
            if set(actual.index) != set(centroids.index):
                raise ValueError("Nhãn cụm không khớp file centroid.")
            for cid in actual.index:
                if int(centroids.loc[cid, "city_count"]) != int(actual_n.loc[cid]):
                    raise ValueError(f"Số đô thị của cụm {cid} không khớp centroid.")
                # K-Means may stop when centres move less than tol, so stored
                # model centroids can differ slightly from exact group means.
                # Profile statistics always use the actual assigned cities.
                difference = np.max(np.abs(
                    actual.loc[cid].to_numpy(dtype=float) -
                    centroids.loc[cid, SHARE_COLS].to_numpy(dtype=float)
                ))
                if difference > 0.01:
                    raise ValueError(
                        f"Tâm cụm {cid} khác quá lớn với trung bình dữ liệu: "
                        f"{difference:.6f}; kiểm tra lại hai file."
                    )
                if difference > 1e-7:
                    print(
                        f"Lưu ý: tâm K-Means cụm {cid} lệch "
                        f"{difference:.6f} so với trung bình đô thị; "
                        "hồ sơ cụm dùng trung bình thực tế."
                    )
    return df


def label_cluster(means: pd.Series) -> str:
    """Create descriptive labels from cluster profiles, not from cluster IDs."""
    ranking = sorted(SECTORS, key=lambda s: float(means[f"share_{s}_2024"]), reverse=True)
    top_two = set(ranking[:2])
    res_tr_sum = float(means["share_residential_2024"] + means["share_transport_2024"])
    if top_two == {"residential", "transport"} and res_tr_sum >= 0.60:
        return "Đô thị thiên về phát thải dân cư và giao thông"
    return f"Đô thị thiên về phát thải {SECTOR_NAMES_VI[ranking[0]].lower()}"


def make_profile(df: pd.DataFrame):
    n_total = len(df)
    result_rows = []
    descriptions = []
    for cid, part in df.groupby("cluster_id", sort=True):
        means = part[SHARE_COLS].mean()
        ranking = sorted(SECTORS, key=lambda s: float(means[f"share_{s}_2024"]), reverse=True)
        name = label_cluster(means)
        dominant_city_sectors = (
            part[SHARE_COLS].to_numpy().argmax(axis=1)
        )
        dominant_counts = pd.Series(
            [SECTORS[idx] for idx in dominant_city_sectors]
        ).value_counts()
        row = {
            "cluster_id": int(cid),
            "cluster_name": name,
            "city_count": int(len(part)),
            "city_percentage": round(100 * len(part) / n_total, 4),
            "dominant_sector_by_mean": ranking[0],
            "top_3_sectors": ", ".join(ranking[:3]),
            "top_sector_dominant_cities_pct": round(
                100 * int(dominant_counts.get(ranking[0], 0)) / len(part), 4
            ),
            "ghg_total_median_2024": float(part["ghg_total_2024"].median()),
            "ghg_total_mean_2024": float(part["ghg_total_2024"].mean()),
            "ghg_total_sum_2024": float(part["ghg_total_2024"].sum()),
            "mean_distance_to_centroid": float(part["distance_to_centroid"].mean()),
        }
        for sector in SECTORS:
            row[f"mean_share_{sector}_pct"] = round(
                100 * float(means[f"share_{sector}_2024"]), 4
            )
            row[f"cities_dominant_{sector}_pct"] = round(
                100 * int(dominant_counts.get(sector, 0)) / len(part), 4
            )
        result_rows.append(row)

        first, second = ranking[:2]
        desc = (
            f"Cụm {cid} gồm {len(part):,} đô thị ({len(part)/n_total:.1%} tổng số). "
            f"Tỷ trọng GHG trung bình nổi bật: "
            f"{SECTOR_NAMES_VI[first]} {100*means[f'share_{first}_2024']:.2f}% "
            f"và {SECTOR_NAMES_VI[second]} {100*means[f'share_{second}_2024']:.2f}%. "
            "Đây là đặc điểm cơ cấu phát thải, không phải bằng chứng về nhu cầu mua giải pháp."
        )
        descriptions.append({
            "cluster_id": int(cid),
            "cluster_name": name,
            "description": desc,
            "city_count": int(len(part)),
            "city_percentage": round(100 * len(part) / n_total, 4),
            "median_ghg_total_2024_source_units": float(part["ghg_total_2024"].median()),
            "sector_share_mean_pct": {
                s: round(100 * float(means[f"share_{s}_2024"]), 4)
                for s in SECTORS
            },
            "top_3_sectors": ranking[:3],
        })
    return pd.DataFrame(result_rows), descriptions


def make_representative_cities(df: pd.DataFrame, profiles: pd.DataFrame) -> pd.DataFrame:
    profile_names = profiles.set_index("cluster_id")["cluster_name"].to_dict()
    cols = [
        "city_id", "city_name", "country_name", "cluster_id",
        "distance_to_centroid", "ghg_total_2024", *SHARE_COLS,
    ]
    chunks = []
    for cid, part in df.groupby("cluster_id", sort=True):
        nearest = part.nsmallest(TOP_N_CITIES, "distance_to_centroid")[cols].copy()
        nearest.insert(4, "cluster_name", profile_names[int(cid)])
        nearest.insert(5, "representative_rank", range(1, len(nearest) + 1))
        chunks.append(nearest)
    return pd.concat(chunks, ignore_index=True)


def export_charts(profiles: pd.DataFrame) -> None:
    ids = profiles["cluster_id"].astype(str).to_list()
    counts = profiles["city_count"].to_numpy()
    fig, ax = plt.subplots(figsize=(8, 4.8))
    bars = ax.bar([f"Cluster {cid}" for cid in ids], counts)
    ax.bar_label(bars, padding=3, fmt="%d")
    ax.set_ylabel("Number of urban centres")
    ax.set_title("Urban centres by emission-profile cluster")
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "cluster_sizes.png", dpi=220, bbox_inches="tight")
    plt.close(fig)

    x = np.arange(len(SECTORS))
    n_clusters = len(profiles)
    width = 0.78 / n_clusters
    fig, ax = plt.subplots(figsize=(12, 5.8))
    for i, row in profiles.reset_index(drop=True).iterrows():
        vals = [row[f"mean_share_{s}_pct"] for s in SECTORS]
        ax.bar(x + (i - (n_clusters - 1) / 2) * width, vals, width,
               label=f"Cluster {int(row['cluster_id'])}")
    ax.set_xticks(x)
    ax.set_xticklabels([s.title() for s in SECTORS], rotation=20, ha="right")
    ax.set_ylabel("Mean share of city emissions (%)")
    ax.set_title("Mean GHG sector shares by cluster (2024)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(OUTPUT_DIR / "cluster_sector_distribution.png", dpi=220, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    df = load_and_validate()
    profiles, descriptions = make_profile(df)
    representative = make_representative_cities(df, profiles)

    profiles.to_csv(OUTPUT_DIR / "cluster_profiles_2024.csv", index=False, encoding="utf-8-sig")
    representative.to_csv(
        OUTPUT_DIR / "representative_cities_2024.csv", index=False, encoding="utf-8-sig"
    )
    payload = {
        "project": "GreenSegment AI",
        "data_year": 2024,
        "analysis": "Profiles of the already-fitted final K-Means clusters",
        "emission_units": "Unit from EDGAR source; verify metadata before naming units",
        "sector_mean_definition": "Mean across city-level GHG sector shares, in percent",
        "notes": [
            "Cluster numbers are arbitrary labels, not rankings.",
            "Sector relevance alone does not establish local technology demand or B2B potential.",
            "Average sector shares do not equal the sector shares of total summed emissions.",
            "The Energy/International sector definitions must be checked against EDGAR metadata.",
        ],
        "clusters": descriptions,
    }
    with (OUTPUT_DIR / "cluster_descriptions.json").open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    export_charts(profiles)
    print("\nGreenSegment AI | Cluster Analysis completed")
    print(f"Cities: {len(df):,} | Clusters: {df['cluster_id'].nunique()}")
    print(profiles[["cluster_id", "cluster_name", "city_count", "city_percentage"]].to_string(index=False))
    print("\nOutputs:")
    for filename in [
        "cluster_profiles_2024.csv", "representative_cities_2024.csv",
        "cluster_sector_distribution.png", "cluster_sizes.png", "cluster_descriptions.json",
    ]:
        print("-", (OUTPUT_DIR / filename).relative_to(ROOT))
    print("\nNote: The input data and the saved K-Means model were not modified.")


if __name__ == "__main__":
    main()
