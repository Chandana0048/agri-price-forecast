import os
import pandas as pd

RAW_DIR = os.path.join("ml", "data", "raw")
OUT_DIR = os.path.join("ml", "data", "processed")
os.makedirs(OUT_DIR, exist_ok=True)

WEATHER_FILE = os.path.join(RAW_DIR, "master_with_weather.csv")
SEASON_FILE  = os.path.join(RAW_DIR, "master_with_seasonal_factors.csv")

OUT_FILE = os.path.join(OUT_DIR, "master_merged_weather_seasonal.csv")

def normalize_cols(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    return df

def main():
    if not os.path.exists(WEATHER_FILE):
        raise FileNotFoundError(f"Missing: {WEATHER_FILE}")
    if not os.path.exists(SEASON_FILE):
        raise FileNotFoundError(f"Missing: {SEASON_FILE}")

    w = pd.read_csv(WEATHER_FILE, low_memory=False)
    s = pd.read_csv(SEASON_FILE, low_memory=False)

    w = normalize_cols(w)
    s = normalize_cols(s)

    # standardize date column name
    # Your commodity dataset used "arrival_date" earlier; keep it
    for df in (w, s):
        if "arrival_date" not in df.columns:
            # try common alternatives
            for alt in ["date", "arrivaldate", "arrival_date_parsed"]:
                if alt in df.columns:
                    df.rename(columns={alt: "arrival_date"}, inplace=True)
                    break

    # Parse dates
    w["arrival_date"] = pd.to_datetime(w["arrival_date"], errors="coerce")
    s["arrival_date"] = pd.to_datetime(s["arrival_date"], errors="coerce")

    # Keys for merge
    keys = ["state", "district", "market", "commodity", "arrival_date"]
    missing_keys = [k for k in keys if k not in w.columns or k not in s.columns]
    if missing_keys:
        raise ValueError(f"Missing merge keys in one file: {missing_keys}")

    # avoid duplicate non-key columns
    dup_cols = set(w.columns).intersection(set(s.columns)) - set(keys)
    # keep weather as base, bring only seasonal columns not in weather
    s2 = s.drop(columns=list(dup_cols), errors="ignore")

    merged = w.merge(s2, on=keys, how="left")

    merged.to_csv(OUT_FILE, index=False)
    print("✅ Saved merged dataset:", OUT_FILE)
    print("Rows:", len(merged), "| Cols:", len(merged.columns))

if __name__ == "__main__":
    main()