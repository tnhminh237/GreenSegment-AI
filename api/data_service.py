"""Read existing GreenSegment CSV/JSON artifacts. No training or database needed."""
from __future__ import annotations

import csv
import json
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
    return {**city, "cluster": cluster, "comparison_percentage_points": comparisons}


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
