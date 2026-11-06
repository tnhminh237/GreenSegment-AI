"""GreenSegment AI - Merge, validate, clean, and engineer 2024 GHG features.

Place this file at GreenSegment AI/src/prepare_data.py and the input files at:
GreenSegment AI/data/raw/ghg_2024_10_cot.csv
GreenSegment AI/data/raw/uc_filtered.csv
Run from GreenSegment AI (or any directory):
    .\\.venv\\Scripts\\python.exe src\\prepare_data.py
"""

from pathlib import Path
import pandas as pd
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
RAW = ROOT / "data" / "raw"
INTERIM = ROOT / "data" / "interim"
PROCESSED = ROOT / "data" / "processed"
KEY = "ID_UC_G0"
CITY = "GC_UCN_MAI_2025"
COUNTRY = "GC_CNT_GAD_2025"
SECTORS = [
    "Agriculture", "Energy", "Industry", "International",
    "Residential", "Transport", "Waste",
]
GHG_COLS = {s: f"EMI_GWP_100_AR5_GHG_{s}_2024" for s in SECTORS}

# Map raw EDGAR/GHS-UCDB headers to readable column names.
# Raw CSV files remain unchanged; all generated CSVs use these names.
RENAME_COLUMNS = {
    KEY: "city_id",
    CITY: "city_name",
    COUNTRY: "country_name",
    "lon": "longitude",
    "lat": "latitude",
    **{raw: f"ghg_{sector.lower()}_2024" for sector, raw in GHG_COLS.items()},
}
NEW_GHG_COLS = [f"ghg_{sector.lower()}_2024" for sector in SECTORS]


def fix_mojibake(value):
    """Fix UTF-8 text accidentally decoded as Latin-1; leave other text intact."""
    if not isinstance(value, str) or not any(x in value for x in ("Ã", "Â")):
        return value
    try:
        return value.encode("latin-1").decode("utf-8")
    except UnicodeError:
        return value


def main():
    INTERIM.mkdir(parents=True, exist_ok=True)
    PROCESSED.mkdir(parents=True, exist_ok=True)

    ghg_path = RAW / "ghg_2024_10_cot.csv"
    geo_path = RAW / "uc_filtered.csv"
    for path in (ghg_path, geo_path):
        if not path.is_file():
            raise FileNotFoundError(f"Missing input file: {path}")

    ghg = pd.read_csv(ghg_path, encoding="utf-8-sig")
    geo = pd.read_csv(geo_path, encoding="utf-8-sig")

    required_ghg = {KEY, CITY, COUNTRY, *GHG_COLS.values()}
    required_geo = {KEY, "lon", "lat"}
    if set(ghg.columns) != required_ghg or len(ghg.columns) != 10:
        raise ValueError(f"Unexpected EDGAR columns. Missing={required_ghg - set(ghg.columns)}; extra={set(ghg.columns) - required_ghg}")
    if set(geo.columns) != required_geo or len(geo.columns) != 3:
        raise ValueError(f"Unexpected GHS-UCDB columns. Missing={required_geo - set(geo.columns)}; extra={set(geo.columns) - required_geo}")

    if ghg[KEY].isna().any() or geo[KEY].isna().any():
        raise ValueError("Missing IDs: cannot safely join")
    if ghg[KEY].duplicated().any() or geo[KEY].duplicated().any():
        raise ValueError("Duplicate IDs: expected one row per urban centre")

    merged = ghg.merge(geo, on=KEY, how="inner", validate="one_to_one")
    if len(merged) != len(ghg) or len(merged) != len(geo):
        raise ValueError("Some IDs could not be matched across both source files")

    # Standardize column names after joining on the original source ID.
    merged = merged.rename(columns=RENAME_COLUMNS)

    merged_path = INTERIM / "greensegment_merged_2024.csv"
    merged.to_csv(merged_path, index=False, encoding="utf-8-sig")

    clean = merged.copy()
    missing_cities = clean["city_name"].isna() | clean["city_name"].astype("string").str.strip().eq("").fillna(False)
    num_missing_cities = int(missing_cities.sum())
    clean["city_name"] = clean["city_name"].astype("string").str.strip()
    clean.loc[missing_cities, "city_name"] = clean.loc[missing_cities, "city_id"].map(
        lambda x: f"Unknown City (ID: {x})"
    )

    old_country = clean["country_name"].copy()
    clean["country_name"] = clean["country_name"].map(fix_mojibake)
    fixed_countries = int((old_country != clean["country_name"]).fillna(False).sum())

    for col in [*NEW_GHG_COLS, "longitude", "latitude"]:
        clean[col] = pd.to_numeric(clean[col], errors="raise")
        if not np.isfinite(clean[col].to_numpy(dtype=float)).all():
            raise ValueError(f"Non-finite numeric values in {col}")
    if (clean[NEW_GHG_COLS] < 0).any().any():
        raise ValueError("Negative GHG emission found; review units/source")
    if not clean["longitude"].between(-180, 180).all() or not clean["latitude"].between(-90, 90).all():
        raise ValueError("Invalid latitude or longitude detected")

    clean_path = PROCESSED / "greensegment_cleaned_2024.csv"
    clean.to_csv(clean_path, index=False, encoding="utf-8-sig")

    features = clean.copy()
    features["ghg_total_2024"] = features[NEW_GHG_COLS].sum(axis=1)
    zero_total_count = int((features["ghg_total_2024"] == 0).sum())
    if zero_total_count:
        raise ValueError(f"{zero_total_count} urban centres have zero total emissions; define policy before share calculation")

    for sector in SECTORS:
        col = f"ghg_{sector.lower()}_2024"
        features[f"share_{sector.lower()}_2024"] = features[col] / features["ghg_total_2024"]
    share_cols = [f"share_{s.lower()}_2024" for s in SECTORS]
    if not np.allclose(features[share_cols].sum(axis=1), 1.0, atol=1e-9):
        raise ValueError("GHG shares do not sum to 1")

    features_path = PROCESSED / "greensegment_features_2024.csv"
    features.to_csv(features_path, index=False, encoding="utf-8-sig")

    print("GreenSegment AI - Data preparation successful")
    print(f"Urban centres: {len(features):,}")
    print(f"Merged columns: {merged.shape[1]} | Feature columns: {features.shape[1]}")
    print(f"Missing city names labeled: {num_missing_cities}")
    print(f"Country names encoding corrected: {fixed_countries}")
    print(f"Zero-total-GHG urban centres: {zero_total_count}")
    print("Generated files:")
    for path in (merged_path, clean_path, features_path):
        print(f"  - {path.relative_to(ROOT)}")
    print("Note: Keep source files unchanged. Confirm EDGAR units and sector definitions before interpreting values.")


if __name__ == "__main__":
    main()
