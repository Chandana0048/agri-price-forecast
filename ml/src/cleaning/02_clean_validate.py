# import os
# import numpy as np
# import pandas as pd

# IN_FILE  = os.path.join("ml", "data", "processed", "master_merged_weather_seasonal.csv")
# OUT_FILE = os.path.join("ml", "data", "processed", "master_clean.csv")

# def normalize_cols(df):
#     df = df.copy()
#     df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
#     return df

# def coerce_numeric(df, cols):
#     for c in cols:
#         if c in df.columns:
#             df[c] = pd.to_numeric(df[c], errors="coerce")
#     return df

# def iqr_cap(series: pd.Series, k=1.5):
#     q1 = series.quantile(0.25)
#     q3 = series.quantile(0.75)
#     iqr = q3 - q1
#     lo = q1 - k * iqr
#     hi = q3 + k * iqr
#     return series.clip(lo, hi)

# def main():
#     if not os.path.exists(IN_FILE):
#         raise FileNotFoundError(f"Run 01_merge_sources.py first. Missing: {IN_FILE}")

#     df = pd.read_csv(IN_FILE, low_memory=False)
#     df = normalize_cols(df)

#     # mandatory columns
#     required = ["state", "district", "market", "commodity", "arrival_date"]
#     for r in required:
#         if r not in df.columns:
#             raise ValueError(f"Missing required column: {r}")

#     df["arrival_date"] = pd.to_datetime(df["arrival_date"], errors="coerce")
#     df = df.dropna(subset=["arrival_date", "state", "market", "commodity"])

#     # prices / arrivals
#     numeric_cols = ["min_price", "max_price", "modal_price", "arrival_quantity", "arrival_qty"]
#     df = coerce_numeric(df, numeric_cols)

#     # unify arrival quantity column
#     if "arrival_quantity" not in df.columns and "arrival_qty" in df.columns:
#         df.rename(columns={"arrival_qty": "arrival_quantity"}, inplace=True)

#     # remove impossible prices
#     if "modal_price" in df.columns:
#         df = df[df["modal_price"] > 0]

#     # Missing value handling
#     # prices: forward-fill within (commodity, market) over time
#     sort_cols = ["commodity", "state", "district", "market", "arrival_date"]
#     df = df.sort_values(sort_cols)

#     group_cols = ["commodity", "state", "district", "market"]

#     if "modal_price" in df.columns:
#         df["modal_price"] = df.groupby(group_cols)["modal_price"].ffill()

#     # weather: fill with state-level daily median if missing
#     weather_cols = ["t2m", "t2m_max", "t2m_min", "prectotcorr", "rh2m", "ws2m"]
#     present_weather = [c for c in weather_cols if c in df.columns]
#     for c in present_weather:
#         df[c] = df.groupby(["state", "arrival_date"])[c].transform(lambda x: x.fillna(x.median()))
#         df[c] = df[c].fillna(df[c].median())

#     # Outlier capping (IQR) for modal_price per group
#     if "modal_price" in df.columns:
#         df["modal_price"] = df.groupby(group_cols)["modal_price"].transform(iqr_cap)

#     # drop rows still missing modal_price
#     df = df.dropna(subset=["modal_price"])

#     df.to_csv(OUT_FILE, index=False)
#     print("✅ Saved cleaned dataset:", OUT_FILE)
#     print("Rows:", len(df), "| Cols:", len(df.columns))

# if __name__ == "__main__":
#     main()

import pandas as pd
import os

RAW_FILE = "ml/data/processed/master_merged_weather_seasonal.csv"
OUT_FILE = "ml/data/processed/master_clean.csv"

def main():
    print("📥 Reading raw dataset...")
    df = pd.read_csv(RAW_FILE, low_memory=False)

    print("Initial shape:", df.shape)

    # -------------------------
    # Drop trash filename columns
    # -------------------------
    junk_cols = [c for c in df.columns if c.endswith(".xlsx")]
    if junk_cols:
        print("🗑 Dropping junk columns:", junk_cols)
        df.drop(columns=junk_cols, inplace=True)

    # -------------------------
    # Standardize column names
    # -------------------------
    df.columns = (
        df.columns
          .str.strip()
          .str.lower()
          .str.replace(" ", "_")
    )

    # -------------------------
    # Convert date
    # -------------------------
    df["arrival_date"] = pd.to_datetime(df["arrival_date"], errors="coerce")

    # -------------------------
    # Numeric columns
    # -------------------------
    num_cols = [
        "min_price","max_price","modal_price",
        "arrival_quantity",
        "t2m","t2m_max","t2m_min",
        "prectotcorr","rh2m","ws2m"
    ]

    for c in num_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    # -------------------------
    # Drop rows without target
    # -------------------------
    df = df.dropna(subset=["modal_price","arrival_date"])

    print("After cleaning shape:", df.shape)

    os.makedirs(os.path.dirname(OUT_FILE), exist_ok=True)
    df.to_csv(OUT_FILE, index=False)

    print("✅ Clean dataset saved:", OUT_FILE)
    print("Columns:", list(df.columns))

if __name__ == "__main__":
    main()