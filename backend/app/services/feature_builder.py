import os
import re
import numpy as np
import pandas as pd
from datetime import datetime
from functools import lru_cache

# Use train.csv (fast) or switch to master file if you want more rows
DATA_PATH = os.getenv("FEATURE_SOURCE_CSV", "ml/data/processed/train.csv")

DATE_COL = "arrival_date"
TARGET = "modal_price"

KEY_COLS = ["state", "market", "commodity"]

# If your engineered dataset includes these one-hot prefixes, we'll set them explicitly.
ONE_HOT_PREFIXES = {
    "state": ["state_", "State_"],
    "market": ["market_", "Market_"],
    "commodity": ["commodity_", "Commodity_"],
}

def _norm(s: str) -> str:
    """
    Normalize text for robust matching:
    - lower
    - trim
    - collapse spaces
    - remove weird punctuation duplicates
    """
    if s is None:
        return ""
    s = str(s).strip().lower()
    s = re.sub(r"\s+", " ", s)
    # normalize common separators
    s = s.replace("&", "and")
    s = s.replace("/", " ")
    s = re.sub(r"[^\w\s\-\(\)]", "", s)  # keep words, spaces, hyphen, parentheses
    s = re.sub(r"\s+", " ", s).strip()
    return s


@lru_cache(maxsize=1)
def _load_df():
    df = pd.read_csv(DATA_PATH, low_memory=False)

    # parse date
    if DATE_COL in df.columns:
        df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")

    # normalize keys
    for c in KEY_COLS:
        if c in df.columns:
            df[c] = df[c].astype(str).map(_norm)

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


def _set_one_hot_from_payload(X: pd.DataFrame, feature_cols: list[str], state: str, market: str, commodity: str):
    """
    If training created dummy columns like state_Tamil Nadu, market_Nasik APMC, etc,
    this sets the matching column to 1 so your feature vector isn't all zeros.
    """
    # work with normalized values (same as df)
    state_n = _norm(state)
    market_n = _norm(market)
    commodity_n = _norm(commodity)

    # build quick lookup from normalized colname -> actual colname
    # (so we can match even if columns have weird spacing/casing)
    norm_col_map = { _norm(c): c for c in feature_cols }

    def try_set(prefixes: list[str], value_norm: str):
        if not value_norm:
            return
        # common patterns in dummy columns:
        # "state_tamil nadu", "state_tamil_nadu", "State_Tamil Nadu"
        candidates = [
            f"{p}{value_norm}" for p in prefixes
        ] + [
            f"{p}{value_norm.replace(' ', '_')}" for p in prefixes
        ] + [
            f"{p}{value_norm.replace(' ', '')}" for p in prefixes
        ]

        for cand in candidates:
            cand_norm = _norm(cand)
            if cand_norm in norm_col_map:
                X.loc[:, norm_col_map[cand_norm]] = 1
                return  # set first best match

    try_set(ONE_HOT_PREFIXES["state"], state_n)
    try_set(ONE_HOT_PREFIXES["market"], market_n)
    try_set(ONE_HOT_PREFIXES["commodity"], commodity_n)


def build_features(payload: dict, feature_cols: list[str]):
    """
    Build features by:
    1) finding the best matching historical row (exact -> state_commodity -> commodity_only)
    2) copying engineered numeric features (lags/rolling/etc) from that row
    3) overwriting date features to requested date
    4) explicitly setting one-hot columns from the requested payload (if present)

    Fallback ladder:
      1) exact            (state+market+commodity)
      2) state_commodity  (state+commodity)
      3) commodity_only   (commodity)
      4) date_only
    Returns: (X_dataframe, fallback_level)
    """
    df = _load_df()

    state = payload.get("state", "")
    market = payload.get("market", "")
    commodity = payload.get("commodity", "")
    arrival_date = payload.get("arrival_date")

    state_n = _norm(state)
    market_n = _norm(market)
    commodity_n = _norm(commodity)

    req_dt = pd.to_datetime(arrival_date, errors="coerce")

    def _filter_series(level: str) -> pd.DataFrame:
        if level == "exact":
            s = df[(df["state"] == state_n) & (df["market"] == market_n) & (df["commodity"] == commodity_n)].copy()
        elif level == "state_commodity":
            s = df[(df["state"] == state_n) & (df["commodity"] == commodity_n)].copy()
        elif level == "commodity_only":
            s = df[(df["commodity"] == commodity_n)].copy()
        else:
            s = df.iloc[0:0].copy()

        if pd.notna(req_dt) and len(s) > 0:
            # prefer past history; if none exists, we will handle later (latest_in_series)
            s = s[s[DATE_COL] <= req_dt]
        return s

    # 1) Try fallbacks
    fallback_level = "exact"
    series = _filter_series("exact")

    if len(series) == 0:
        fallback_level = "state_commodity"
        series = _filter_series("state_commodity")

    if len(series) == 0:
        fallback_level = "commodity_only"
        series = _filter_series("commodity_only")

    # If req_dt existed but filtering removed all rows (no earlier history),
    # we should still use the latest row in that series rather than date_only.
    used_latest_in_series = False
    if len(series) == 0 and fallback_level in ("exact", "state_commodity", "commodity_only"):
        # try again WITHOUT date constraint
        if fallback_level == "exact":
            series2 = df[(df["state"] == state_n) & (df["market"] == market_n) & (df["commodity"] == commodity_n)].copy()
        elif fallback_level == "state_commodity":
            series2 = df[(df["state"] == state_n) & (df["commodity"] == commodity_n)].copy()
        else:
            series2 = df[(df["commodity"] == commodity_n)].copy()

        if len(series2) > 0:
            series = series2.sort_values(DATE_COL)
            used_latest_in_series = True

    if len(series) == 0:
        # 2) date_only final fallback
        fallback_level = "date_only"
        base = _date_features(arrival_date)
        X = pd.DataFrame([base])
    else:
        # 3) choose last historical row
        series = series.sort_values(DATE_COL)
        row = series.iloc[-1:].copy()

        if used_latest_in_series and fallback_level != "date_only":
            # keep original ladder label if it wasn't exact,
            # but signal that we used "latest row" instead of <= req_dt
            fallback_level = "latest_in_series" if fallback_level == "exact" else fallback_level

        # drop target if exists
        if TARGET in row.columns:
            row = row.drop(columns=[TARGET], errors="ignore")

        # overwrite date-based features with requested date
        dfeat = _date_features(arrival_date)
        for k, v in dfeat.items():
            row[k] = v

        X = row

    # 4) Ensure all expected columns exist
    for c in feature_cols:
        if c not in X.columns:
            X[c] = 0

    X = X[feature_cols].copy()

    # 5) Set one-hot columns from the requested payload (if model expects them)
    _set_one_hot_from_payload(X, feature_cols, state, market, commodity)

    # 6) Make numeric safe
    for c in X.columns:
        if X[c].dtype == "object":
            X[c] = pd.to_numeric(X[c], errors="coerce").fillna(0)

    return X, fallback_level