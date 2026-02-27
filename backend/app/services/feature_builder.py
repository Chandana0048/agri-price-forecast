import os
import numpy as np
import pandas as pd
from datetime import datetime
from functools import lru_cache

# Use train.csv (fast) or switch to master file if you want more rows
DATA_PATH = os.getenv("FEATURE_SOURCE_CSV", "ml/data/processed/train.csv")

DATE_COL = "arrival_date"
TARGET = "modal_price"

KEY_COLS = ["state", "market", "commodity"]

@lru_cache(maxsize=1)
def _load_df():
    df = pd.read_csv(DATA_PATH, low_memory=False)

    # parse date
    if DATE_COL in df.columns:
        df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")

    # keep only valid rows
    for c in KEY_COLS:
        if c in df.columns:
            df[c] = df[c].astype(str).str.strip()

    df = df.dropna(subset=[DATE_COL] + [c for c in KEY_COLS if c in df.columns])
    df = df.sort_values(DATE_COL)
    return df


def _date_features(arrival_date: str) -> dict:
    d = datetime.strptime(arrival_date, "%Y-%m-%d")
    return {
        "year": d.year,
        "month": d.month,
        "weekofyear": int(d.strftime("%V")),
        "day_of_week": d.weekday(),
        "quarter": (d.month - 1) // 3 + 1,
        "is_weekend": 1 if d.weekday() >= 5 else 0,
        "month_sin": float(np.sin(2 * np.pi * (d.month / 12))),
        "month_cos": float(np.cos(2 * np.pi * (d.month / 12))),
        "dow_sin": float(np.sin(2 * np.pi * (d.weekday() / 7))),
        "dow_cos": float(np.cos(2 * np.pi * (d.weekday() / 7))),
    }


def build_features(payload: dict, feature_cols: list[str]):
    """
    Build features by grabbing the closest historical row and reusing engineered features.
    Fallback ladder (when exact combo has 0 history):
      1) exact: state+market+commodity
      2) state+commodity (any market in state)
      3) commodity (any state/market)
      4) date_only
    Returns: (X_dataframe, fallback_level)
    """
    df = _load_df()

    state = str(payload.get("state", "")).strip()
    market = str(payload.get("market", "")).strip()
    commodity = str(payload.get("commodity", "")).strip()
    arrival_date = payload.get("arrival_date")

    req_dt = pd.to_datetime(arrival_date, errors="coerce")

    def _filter_series(level: str) -> pd.DataFrame:
        if level == "exact":
            s = df[(df["state"] == state) & (df["market"] == market) & (df["commodity"] == commodity)].copy()
        elif level == "state+commodity":
            s = df[(df["state"] == state) & (df["commodity"] == commodity)].copy()
        elif level == "commodity":
            s = df[(df["commodity"] == commodity)].copy()
        else:
            s = df.iloc[0:0].copy()

        if req_dt is not pd.NaT and len(s) > 0:
            s = s[s[DATE_COL] <= req_dt]
        return s

    fallback_level = "exact"
    series = _filter_series("exact")

    if len(series) == 0:
        fallback_level = "state+commodity"
        series = _filter_series("state+commodity")

    if len(series) == 0:
        fallback_level = "commodity"
        series = _filter_series("commodity")

    if len(series) == 0:
        fallback_level = "date_only"
        base = _date_features(arrival_date)
        X = pd.DataFrame([base])
    else:
        row = series.sort_values(DATE_COL).iloc[-1:].copy()

        # drop target if exists
        if TARGET in row.columns:
            row = row.drop(columns=[TARGET], errors="ignore")

        # overwrite date-based features
        dfeat = _date_features(arrival_date)
        for k, v in dfeat.items():
            row[k] = v

        X = row

    # Ensure all expected columns exist
    for c in feature_cols:
        if c not in X.columns:
            X[c] = 0

    X = X[feature_cols].copy()

    # Make numeric safe
    for c in X.columns:
        if X[c].dtype == "object":
            X[c] = pd.to_numeric(X[c], errors="coerce").fillna(0)

    return X, fallback_level