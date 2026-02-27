import os
import pandas as pd
from functools import lru_cache

DATA_PATH = os.getenv("META_CSV_PATH", "ml/data/processed/train.csv")

NEEDED_COLS = ["state", "district", "market", "commodity", "arrival_date", "modal_price", "arrivals"]

@lru_cache(maxsize=1)
def _load_df():
    df = pd.read_csv(DATA_PATH, low_memory=False)

    # keep only columns that exist
    cols = [c for c in NEEDED_COLS if c in df.columns]
    df = df[cols].copy()

    if "arrival_date" in df.columns:
        df["arrival_date"] = pd.to_datetime(df["arrival_date"], errors="coerce")
    if "modal_price" in df.columns:
        df["modal_price"] = pd.to_numeric(df["modal_price"], errors="coerce")

    if "arrivals" in df.columns:
        df["arrivals"] = pd.to_numeric(df["arrivals"], errors="coerce")

    df = df.dropna(subset=[c for c in ["state", "market", "commodity"] if c in df.columns])
    return df

def states():
    df = _load_df()
    return sorted(df["state"].dropna().unique().tolist())

def commodities():
    df = _load_df()
    return sorted(df["commodity"].dropna().unique().tolist())

def markets(state: str | None = None):
    df = _load_df()
    if state:
        df = df[df["state"] == state]
    return sorted(df["market"].dropna().unique().tolist())

def districts(state: str | None = None):
    df = _load_df()
    if "district" not in df.columns:
        return []
    if state:
        df = df[df["state"] == state]
    return sorted(df["district"].dropna().unique().tolist())

def top_markets(state: str | None = None, commodity: str | None = None, k: int = 10):
    """
    Returns top markets by activity:
    - If arrivals column exists: use total arrivals
    - else: use record count
    Also returns avg_price for display + chart.
    """
    df = _load_df()

    if state:
        df = df[df["state"] == state]
    if commodity:
        df = df[df["commodity"] == commodity]

    if "modal_price" in df.columns:
        df = df.dropna(subset=["modal_price"])

    if "arrivals" in df.columns and df["arrivals"].notna().any():
        grp = df.groupby("market", as_index=False).agg(
            activity=("arrivals", "sum"),
            avg_price=("modal_price", "mean"),
            records=("market", "size"),
        )
    else:
        grp = df.groupby("market", as_index=False).agg(
            activity=("market", "size"),
            avg_price=("modal_price", "mean"),
            records=("market", "size"),
        )

    grp = grp.sort_values("activity", ascending=False).head(int(k))
    # safe rounding for UI
    grp["avg_price"] = grp["avg_price"].round(2)
    return grp.to_dict(orient="records")