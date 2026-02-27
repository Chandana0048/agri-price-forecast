import os
import numpy as np
import pandas as pd

IN_FILE  = os.path.join("ml", "data", "processed", "master_clean.csv")
OUT_FILE = os.path.join("ml", "data", "processed", "master_features.csv")

def main():
    if not os.path.exists(IN_FILE):
        raise FileNotFoundError(f"Run 02_clean_validate.py first. Missing: {IN_FILE}")

    df = pd.read_csv(IN_FILE, low_memory=False)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    df["arrival_date"] = pd.to_datetime(df["arrival_date"], errors="coerce")
    df = df.dropna(subset=["arrival_date"])

    df = df.sort_values(["commodity", "state", "district", "market", "arrival_date"])
    group_cols = ["commodity", "state", "district", "market"]

    # basic time features
    df["month"] = df["arrival_date"].dt.month
    df["day_of_week"] = df["arrival_date"].dt.dayofweek
    df["weekofyear"] = df["arrival_date"].dt.isocalendar().week.astype(int)

    # cyclical encoding
    df["month_sin"] = np.sin(2 * np.pi * df["month"] / 12)
    df["month_cos"] = np.cos(2 * np.pi * df["month"] / 12)
    df["dow_sin"] = np.sin(2 * np.pi * df["day_of_week"] / 7)
    df["dow_cos"] = np.cos(2 * np.pi * df["day_of_week"] / 7)

    # market frequency encoding (how active a market is)
    df["market_freq"] = df.groupby("market")["arrival_date"].transform("count")

    # arrivals normalization (safe)
    if "arrival_quantity" in df.columns:
        df["arrival_quantity"] = pd.to_numeric(df["arrival_quantity"], errors="coerce")
        df["arrival_qty_log1p"] = np.log1p(df["arrival_quantity"].fillna(0))
        df["arrival_qty_z"] = df.groupby(["commodity", "state"])["arrival_quantity"].transform(
            lambda x: (x - x.mean()) / (x.std() + 1e-9)
        )

    # lag features (target)
    for lag in [1, 3, 7]:
        df[f"modal_lag_{lag}"] = df.groupby(group_cols)["modal_price"].shift(lag)

    # rolling features (shifted to prevent leakage)
    shifted = df.groupby(group_cols)["modal_price"].shift(1)
    df["modal_roll_mean_7"] = shifted.groupby(df[group_cols].apply(tuple, axis=1)).rolling(7).mean().reset_index(level=0, drop=True)
    df["modal_roll_std_7"]  = shifted.groupby(df[group_cols].apply(tuple, axis=1)).rolling(7).std().reset_index(level=0, drop=True)

    # weather interactions (if present)
    if "t2m_max" in df.columns and "t2m_min" in df.columns:
        df["temp_range"] = df["t2m_max"] - df["t2m_min"]

    if "t2m" in df.columns and "rh2m" in df.columns:
        df["temp_x_humidity"] = df["t2m"] * df["rh2m"]

    if "prectotcorr" in df.columns:
        df["rain_lag_1"] = df.groupby(["state", "district"])["prectotcorr"].shift(1)

    # drop rows where lags not available
    df = df.dropna(subset=["modal_lag_7"])

    df.to_csv(OUT_FILE, index=False)
    print("✅ Saved feature dataset:", OUT_FILE)
    print("Rows:", len(df), "| Cols:", len(df.columns))

if __name__ == "__main__":
    main()