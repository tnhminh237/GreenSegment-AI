
from pathlib import Path
import pandas as pd
from sklearn.model_selection import train_test_split

# =====================================
# 1. CẤU HÌNH
# =====================================

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "processed"

INPUT_FILE = DATA_DIR / "greensegment_features_2024.csv"
TRAIN_FILE = DATA_DIR / "greensegment_train_2024.csv"
TEST_FILE = DATA_DIR / "greensegment_test_2024.csv"

TEST_SIZE = 0.2
RANDOM_STATE = 42

# =====================================
# 2. ĐỌC VÀ KIỂM TRA DỮ LIỆU
# =====================================

df = pd.read_csv(INPUT_FILE, encoding="utf-8-sig")

print("Original dataset:", df.shape)

if df.isna().any().any():
    raise ValueError("Dataset contains missing values.")

if df["city_id"].duplicated().any():
    raise ValueError("Duplicate city_id detected.")

# =====================================
# 3. CHIA TRAIN / TEST
# =====================================

train_df, test_df = train_test_split(
    df,
    test_size=TEST_SIZE,
    random_state=RANDOM_STATE,
    shuffle=True
)

# Đặt lại index sau khi chia
train_df = train_df.reset_index(drop=True)
test_df = test_df.reset_index(drop=True)

# =====================================
# 4. KIỂM TRA KẾT QUẢ
# =====================================

train_ids = set(train_df["city_id"])
test_ids = set(test_df["city_id"])

assert train_ids.isdisjoint(test_ids), (
    "Train and Test contain overlapping city IDs."
)

assert len(train_df) + len(test_df) == len(df), (
    "Number of rows does not match original dataset."
)

assert train_ids | test_ids == set(df["city_id"]), (
    "Some city IDs were lost."
)

# =====================================
# 5. LƯU DỮ LIỆU
# =====================================

train_df.to_csv(
    TRAIN_FILE,
    index=False,
    encoding="utf-8-sig"
)

test_df.to_csv(
    TEST_FILE,
    index=False,
    encoding="utf-8-sig"
)

# =====================================
# 6. HIỂN THỊ KẾT QUẢ
# =====================================

print("\nDATA SPLIT COMPLETED")
print("-" * 40)

print(f"Total cities: {len(df):,}")
print(f"Train: {len(train_df):,} ({len(train_df)/len(df):.1%})")
print(f"Test: {len(test_df):,} ({len(test_df)/len(df):.1%})")

print(f"\nTrain shape: {train_df.shape}")
print(f"Test shape: {test_df.shape}")

print("\nSaved files:")
print(TRAIN_FILE)
print(TEST_FILE)
