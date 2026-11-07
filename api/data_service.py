"""Read existing GreenSegment CSV/JSON artifacts. No training or database needed."""
from __future__ import annotations

import csv
import json
import math
import statistics
from bisect import bisect_right
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CITY_PATH = ROOT / "data" / "processed" / "greensegment_clusters_2024.csv"
PROFILE_PATH = ROOT / "reports" / "cluster_analysis" / "cluster_profiles_2024.csv"
DESCRIPTION_PATH = ROOT / "reports" / "cluster_analysis" / "cluster_descriptions.json"
CATALOG_PATH = ROOT / "data" / "reference" / "green_solutions.json"

SECTORS = ("agriculture", "energy", "industry", "international", "residential", "transport", "waste")
SECTOR_LABELS = {
    "agriculture": "Nông nghiệp", "energy": "Năng lượng", "industry": "Công nghiệp",
    "international": "Quốc tế", "residential": "Dân cư", "transport": "Giao thông", "waste": "Chất thải",
}
CLUSTER_COLORS = {0: "#3b82f6", 1: "#f59e0b", 2: "#10b981"}


def _read_csv(path: Path) -> list[dict[str, str]]:
    if not path.is_file():
        raise FileNotFoundError(f"Thiếu dữ liệu: {path.relative_to(ROOT)}")
    with path.open("r", encoding="utf-8-sig", newline="") as handle:
        return list(csv.DictReader(handle))


def _read_json(path: Path) -> dict[str, Any]:
    if not path.is_file():
        raise FileNotFoundError(f"Thiếu dữ liệu: {path.relative_to(ROOT)}")
    return json.loads(path.read_text(encoding="utf-8-sig"))


def _as_number(value: str | float | None) -> float:
    return float(value or 0)


@lru_cache(maxsize=1)
def all_cities() -> tuple[dict[str, Any], ...]:
    cities = []
    for row in _read_csv(CITY_PATH):
        shares = {sector: round(_as_number(row[f"share_{sector}_2024"]) * 100, 4) for sector in SECTORS}
        emissions = {sector: _as_number(row[f"ghg_{sector}_2024"]) for sector in SECTORS}
        cities.append({
            "city_id": str(row["city_id"]),
            "city_name": row["city_name"],
            "country_name": row["country_name"],
            "latitude": _as_number(row["latitude"]),
            "longitude": _as_number(row["longitude"]),
            "cluster_id": int(row["cluster_id"]),
            "ghg_total_2024": _as_number(row["ghg_total_2024"]),
            "distance_to_centroid": _as_number(row.get("distance_to_centroid")),
            "shares_percent": shares,
            "emissions_by_sector": emissions,
            "dominant_sector": max(SECTORS, key=lambda item: shares[item]),
        })
    # The first page offers cities with larger reported emissions, not a ranking of opportunity.
    cities.sort(key=lambda city: (-city["ghg_total_2024"], city["city_id"]))
    return tuple(cities)


@lru_cache(maxsize=1)
def all_clusters() -> tuple[dict[str, Any], ...]:
    descriptions = _read_json(DESCRIPTION_PATH)
    by_id = {int(row["cluster_id"]): row for row in descriptions.get("clusters", [])}
    clusters = []
    for row in _read_csv(PROFILE_PATH):
        cluster_id = int(row["cluster_id"])
        clusters.append({
            "cluster_id": cluster_id,
            "cluster_name": row["cluster_name"],
            "short_name": {0: "Dân cư · Giao thông", 1: "Công nghiệp", 2: "Năng lượng"}.get(cluster_id, row["cluster_name"]),
            "color": CLUSTER_COLORS.get(cluster_id, "#64748b"),
            "city_count": int(row["city_count"]),
            "city_percentage": _as_number(row["city_percentage"]),
            "ghg_total_median_2024": _as_number(row["ghg_total_median_2024"]),
            "mean_sector_shares_percent": {
                sector: _as_number(row[f"mean_share_{sector}_pct"]) for sector in SECTORS
            },
            "description": by_id.get(cluster_id, {}).get("description", ""),
        })
    return tuple(sorted(clusters, key=lambda item: item["cluster_id"]))


@lru_cache(maxsize=1)
def all_countries() -> tuple[dict[str, Any], ...]:
    counts = Counter(city["country_name"] for city in all_cities())
    return tuple({"name": name, "count": count} for name, count in sorted(counts.items()))


def filter_cities(
    search: str | None = None, country: str | None = None,
    cluster_id: int | None = None, sector: str | None = None,
) -> list[dict[str, Any]]:
    needle = (search or "").strip().casefold()
    result = []
    for city in all_cities():
        if needle and needle not in city["city_name"].casefold() and needle not in city["country_name"].casefold():
            continue
        if country and city["country_name"] != country:
            continue
        if cluster_id is not None and city["cluster_id"] != cluster_id:
            continue
        if sector and city["dominant_sector"] != sector:
            continue
        result.append(city)
    return result


def compact_city(city: dict[str, Any]) -> dict[str, Any]:
    return {key: city[key] for key in (
        "city_id", "city_name", "country_name", "cluster_id", "latitude", "longitude",
        "ghg_total_2024", "dominant_sector",
    )}


def city_details(city_id: str) -> dict[str, Any] | None:
    city = next((item for item in all_cities() if item["city_id"] == city_id), None)
    if city is None:
        return None
    cluster = next((cluster for cluster in all_clusters() if cluster["cluster_id"] == city["cluster_id"]), None)
    comparisons = {}
    if cluster:
        for sector in SECTORS:
            comparisons[sector] = round(
                city["shares_percent"][sector] - cluster["mean_sector_shares_percent"][sector], 4
            )
    return {**city, "cluster": cluster, "comparison_percentage_points": comparisons,
            "analysis": city_analysis(city_id)}


def overview(country: str | None = None, cluster_id: int | None = None, sector: str | None = None) -> dict[str, Any]:
    filtered = filter_cities(country=country, cluster_id=cluster_id, sector=sector)
    count = len(filtered)
    counts = Counter(row["cluster_id"] for row in filtered)
    means = {
        s: round(sum(row["shares_percent"][s] for row in filtered) / count, 4) if count else 0
        for s in SECTORS
    }
    groups = []
    for cluster in all_clusters():
        n = counts.get(cluster["cluster_id"], 0)
        group_cities = (row for row in filtered if row["cluster_id"] == cluster["cluster_id"])
        sums = {s: 0.0 for s in SECTORS}
        for city in group_cities:
            for s in SECTORS:
                sums[s] += city["shares_percent"][s]
        groups.append({
            **cluster,
            "filtered_count": n,
            "filtered_percentage": round(100 * n / count, 2) if count else 0,
            "filtered_mean_sector_shares_percent": {
                s: round(sums[s] / n, 4) if n else 0 for s in SECTORS
            },
        })
    return {
        "total_cities": len(all_cities()),
        "filtered_cities": count,
        "total_countries": len(all_countries()),
        "total_clusters": len(all_clusters()),
        "selected_mean_sector_shares_percent": means,
        "clusters": groups,
        "filter": {"country": country, "cluster_id": cluster_id, "sector": sector},
        "units_note": "Đơn vị GHG gốc EDGAR; chưa xác minh để chuyển sang tCO₂e.",
    }


def map_points(country: str | None, cluster_id: int | None, sector: str | None, limit: int = 5000) -> dict[str, Any]:
    filtered = [city for city in filter_cities(country=country, cluster_id=cluster_id, sector=sector)
                if -90 <= city["latitude"] <= 90 and -180 <= city["longitude"] <= 180]
    total = len(filtered)
    # A representative, deterministic sample from the existing dataset; all filtered cities remain searchable.
    points = filtered if total <= limit else [filtered[i * total // limit] for i in range(limit)]
    return {
        "total_matching": total,
        "shown": len(points),
        "sampled": total > limit,
        "points": [compact_city(city) for city in points],
    }


def solutions_catalog() -> dict[str, Any]:
    return _read_json(CATALOG_PATH)


def status() -> dict[str, Any]:
    files = {"cities": CITY_PATH, "clusters": PROFILE_PATH, "descriptions": DESCRIPTION_PATH,
             "catalog": CATALOG_PATH, "advisor_script": ROOT / "src" / "gemini_advisor.py"}
    return {"ok": all(path.is_file() for path in files.values()),
            "files": {name: path.is_file() for name, path in files.items()}}


def _distribution(values: list[float]) -> dict[str, float]:
    """Population dispersion; linear quantiles at (n-1)*p, like pandas default."""
    ordered = sorted(values)

    def quantile(p: float) -> float:
        position = (len(ordered) - 1) * p
        lower = math.floor(position)
        upper = math.ceil(position)
        return ordered[lower] + (ordered[upper] - ordered[lower]) * (position - lower)

    q1, q3 = quantile(.25), quantile(.75)
    return {"mean": statistics.fmean(values), "median": statistics.median(values),
            "std": statistics.pstdev(values), "min": ordered[0], "max": ordered[-1],
            "q1": q1, "q3": q3, "iqr": q3 - q1, "p90": quantile(.9), "p95": quantile(.95)}


@lru_cache(maxsize=1)
def cluster_explorer() -> dict[str, Any]:
    """Read frozen training artifacts, validate geometry, then describe all cities."""
    columns = [f"share_{s}_2024" for s in SECTORS]
    metadata = _read_json(ROOT / "models" / "kmeans_metadata.json")
    if (metadata.get("algorithm") != "KMeans" or metadata.get("k") != 3
            or metadata.get("feature_columns_ordered") != columns
            or metadata.get("feature_description") != "Raw GHG sector shares (0-1); no scaling/PCA"):
        raise ValueError("Tiền xử lý mô hình không phù hợp với phép tính tỷ trọng trực tiếp.")
    rows = _read_csv(CITY_PATH)
    if len(rows) != 11422 or metadata.get("training_rows") != len(rows):
        raise ValueError("Số đô thị không khớp 11.422 đô thị của mô hình.")
    if len({r["city_id"] for r in rows}) != len(rows) or any(not r["city_id"] for r in rows):
        raise ValueError("city_id thiếu hoặc trùng lặp.")
    centers = {int(r["cluster_id"]): r for r in _read_csv(
        ROOT / "reports" / "cluster_analysis" / "cluster_centroids_2024.csv")}
    groups = {i: [] for i in range(3)}
    if set(centers) != set(groups):
        raise ValueError("Tâm cụm phải có đủ mã 0, 1, 2.")
    max_distance_error = 0.0
    for row in rows:
        cid = int(row["cluster_id"])
        if cid not in groups:
            raise ValueError("Mã cụm không hợp lệ.")
        x = [float(row[c]) for c in columns]
        center = [float(centers[cid][c]) for c in columns]
        if (not all(math.isfinite(v) and -1e-10 <= v <= 1 + 1e-10 for v in x + center)
                or not math.isclose(sum(x), 1, abs_tol=1e-6)
                or not math.isclose(sum(center), 1, abs_tol=1e-6)):
            raise ValueError("Tỷ trọng hoặc tâm cụm không hợp lệ.")
        distance = math.dist(x, center)
        saved = float(row["distance_to_centroid"])
        if not math.isfinite(saved) or not math.isclose(distance, saved, abs_tol=1e-8):
            raise ValueError("Khoảng cách lưu sẵn không khớp tâm cụm trong không gian tỷ trọng.")
        max_distance_error = max(max_distance_error, abs(distance - saved))
        groups[cid].append((x, distance))
    profiles = {c["cluster_id"]: c for c in all_clusters()}
    clusters = []
    for cid, items in groups.items():
        if not items or len(items) != int(centers[cid]["city_count"]):
            raise ValueError("Quy mô cụm không khớp báo cáo tâm cụm.")
        sector_stats = {s: _distribution([x[i] * 100 for x, _ in items])
                        for i, s in enumerate(SECTORS)}
        centroid = {s: float(centers[cid][columns[i]]) * 100 for i, s in enumerate(SECTORS)}
        clusters.append({"cluster_id": cid, "cluster_name": profiles[cid]["cluster_name"],
                         "short_name": profiles[cid]["short_name"], "color": CLUSTER_COLORS[cid],
                         "city_count": len(items), "city_percentage": len(items) / len(rows) * 100,
                         "centroid_percent": centroid, "sector_statistics_percent": sector_stats,
                         "mean_sector_shares_percent": {s: v["mean"] for s, v in sector_stats.items()},
                         "centroid_mean_max_gap_pp": max(abs(centroid[s] - sector_stats[s]["mean"]) for s in SECTORS),
                         "distance_statistics": _distribution([d for _, d in items])})
    for cluster in clusters:
        cluster["comparison_percentage_points"] = {
            str(other["cluster_id"]): {s: cluster["mean_sector_shares_percent"][s] - other["mean_sector_shares_percent"][s]
                                       for s in SECTORS}
            for other in clusters if other["cluster_id"] != cluster["cluster_id"]}
    return {"year": 2024, "total_cities": len(rows), "clusters": clusters,
            "sector_comparison": {s: {"highest_mean_cluster_id": max(clusters, key=lambda c: c["mean_sector_shares_percent"][s])["cluster_id"],
                                        "mean_range_pp": max(c["mean_sector_shares_percent"][s] for c in clusters) - min(c["mean_sector_shares_percent"][s] for c in clusters)} for s in SECTORS},
            "methodology": {"features": columns, "preprocessing": metadata["feature_description"],
                            "centroid_source": "reports/cluster_analysis/cluster_centroids_2024.csv",
                            "training_source": "src/finalize_kmeans.py",
                            "distance": "Euclidean on raw shares (0–1); dimensionless",
                            "std_ddof": 0, "quantiles": "linear, position=(n-1)*p",
                            "distance_max_absolute_error": max_distance_error,
                            "notes": ["Tâm được đọc từ kết quả K-Means; trung bình được tính độc lập từ nhãn cuối cùng. Hai giá trị có thể lệch nhẹ do điều kiện dừng của mô hình.",
                                      "Trung bình tỷ trọng theo đô thị, không gia quyền theo tổng phát thải.",
                                      "Độ lệch chuẩn và IQR tỷ trọng tính bằng điểm phần trăm; khoảng cách dùng tỷ trọng 0–1.",
                                      "Phân cụm mô tả cơ cấu năm 2024, không suy ra nhân quả, mức phát thải tuyệt đối hay thứ hạng xanh.",
                                      "K=3 cố định; mã cụm tùy ý; dữ liệu tổng hợp có sai số và không mô tả mọi đô thị giống nhau."]}}


@lru_cache(maxsize=1)
def _city_analysis_inputs():
    # cluster_explorer validates every stored distance against the saved centers.
    clusters = {c["cluster_id"]: c for c in cluster_explorer()["clusters"]}
    rows = _read_csv(CITY_PATH)
    distances = {cid: [] for cid in clusters}
    for row in rows:
        distances[int(row["cluster_id"])].append(float(row["distance_to_centroid"]))
    return ({row["city_id"]: row for row in rows},
            {cid: sorted(values) for cid, values in distances.items()}, clusters)


def city_analysis(city_id: str) -> dict[str, Any] | None:
    """Full-precision city metrics; never derive differences from rounded shares."""
    rows, distances, clusters = _city_analysis_inputs()
    row = rows.get(city_id)
    if row is None:
        return None
    cid = int(row["cluster_id"])
    cluster = {key: clusters[cid][key] for key in (
        "cluster_id", "cluster_name", "short_name", "color", "city_count", "centroid_percent",
        "sector_statistics_percent", "mean_sector_shares_percent", "centroid_mean_max_gap_pp", "distance_statistics")}
    shares = {s: float(row[f"share_{s}_2024"]) * 100 for s in SECTORS}
    emissions = {s: float(row[f"ghg_{s}_2024"]) for s in SECTORS}
    total = float(row["ghg_total_2024"])
    if (not math.isfinite(total) or total <= 0
            or not all(math.isfinite(v) and v >= 0 for v in emissions.values())
            or not math.isclose(sum(emissions.values()), total, rel_tol=1e-6)
            or any(not math.isclose(emissions[s] / total * 100, shares[s], abs_tol=1e-6) for s in SECTORS)):
        raise ValueError("Phát thải tuyệt đối và tỷ trọng đô thị không khớp dữ liệu gốc.")
    differences = {s: shares[s] - cluster["centroid_percent"][s] for s in SECTORS}
    distance = float(row["distance_to_centroid"])
    values = distances[cid]
    count_le = bisect_right(values, distance)
    median = cluster["distance_statistics"]["median"]
    if math.isclose(distance, median, abs_tol=1e-12):
        distance_summary = "Khoảng cách xấp xỉ trung vị của cụm."
    elif distance < median:
        distance_summary = "Khoảng cách nhỏ hơn trung vị: cơ cấu đô thị gần tâm hơn mức giữa của cụm."
    else:
        distance_summary = "Khoảng cách lớn hơn trung vị: cơ cấu đô thị xa tâm hơn mức giữa của cụm."
    return {"year": 2024, "city_id": city_id, "city_name": row["city_name"],
            "country_name": row["country_name"], "cluster_id": cid,
            "ghg_total_2024": total, "emissions_by_sector": emissions, "shares_percent": shares,
            "cluster": cluster, "comparison_to_centroid_pp": differences,
            "top_sectors": sorted(SECTORS, key=lambda s: shares[s], reverse=True)[:3],
            "notable_differences": [{"sector": s, "difference_pp": differences[s]}
                                    for s in sorted(SECTORS, key=lambda s: abs(differences[s]), reverse=True)[:3]],
            "distance_to_centroid": distance,
            "position_in_cluster": {"reference_city_count": len(values),
                                    "count_at_or_below": count_le,
                                    "percentile_rank_percent": 100 * count_le / len(values),
                                    "summary": distance_summary,
                                    "method": "100 * count(distance <= city_distance) / cluster_city_count; includes self and ties",
                                    "note": "Vị trí thực nghiệm trong cụm: phân vị cao hơn nghĩa là xa tâm hơn so với nhiều thành viên. Không phải xác suất, kiểm định thống kê hoặc kết luận ngoại lệ."},
            "methodology": {"emission_units_verified": False,
                            "emissions_unit": "Đơn vị gốc EDGAR, chưa xác minh; không chuyển đổi sang tCO₂e.",
                            "distance": "Euclid trên 7 tỷ trọng gốc 0–1, không scaling/PCA; không có đơn vị.",
                            "comparison": "Chênh lệch so với tâm K-Means đã lưu, không phải trung bình theo nhãn cuối cùng.",
                            "dispersion": "Độ lệch chuẩn tổng thể ddof=0; IQR và chênh lệch tỷ trọng tính bằng điểm phần trăm.",
                            "scope": "Đặc trưng của cụm toàn bộ đô thị; không thay đổi theo bộ lọc tra cứu.",
                            "limits": "K=3 cố định, dữ liệu 2024; cơ cấu khác lượng tuyệt đối. Không suy ra nguyên nhân, chất lượng môi trường, nhu cầu thị trường hoặc tính khả thi công nghệ."}}
