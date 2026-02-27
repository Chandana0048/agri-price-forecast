import os
import re
import sys
import argparse
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv
from sqlalchemy import text

# ----------------------------
# Helpers
# ----------------------------
def clean_col(col: str) -> str:
    col = col.strip()
    col = col.lower()
    col = re.sub(r"[^\w]+", "_", col)   # replace non-word chars with _
    col = re.sub(r"_+", "_", col)       # collapse multiple underscores
    col = col.strip("_")
    return col

def detect_and_cast(df: pd.DataFrame) -> pd.DataFrame:
    """
    Best-effort type casting for common columns in your dataset.
    Adjust here if your column names differ.
    """
    # Date columns (common variants)
    for c in ["arrival_date", "date", "arrivaldate"]:
        if c in df.columns:
            df[c] = pd.to_datetime(df[c], errors="coerce")

    # Common numeric columns
    numeric_cols = [
        "min_price", "max_price", "modal_price",
        "arrival_quantity",
        "t2m", "t2m_max", "t2m_min", "prectotcorr", "rh2m", "ws2m"
    ]
    for c in numeric_cols:
        if c in df.columns:
            df[c] = pd.to_numeric(df[c], errors="coerce")

    return df

def build_engine():
    load_dotenv()

    # Prefer DATABASE_URL if you have it
    db_url = os.getenv("DATABASE_URL", "").strip()
    if db_url:
        return create_engine(db_url, pool_pre_ping=True)

    # Otherwise build from parts
    host = os.getenv("PGHOST", "localhost")
    port = os.getenv("PGPORT", "5432")
    db   = os.getenv("PGDATABASE", "agri_price")
    user = os.getenv("PGUSER", "agri_user")
    pwd  = os.getenv("PGPASSWORD", "agri123")

    return create_engine(
        f"postgresql+psycopg2://{user}:{pwd}@{host}:{port}/{db}",
        pool_pre_ping=True
    )

# ----------------------------
# Main
# ----------------------------
def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--csv",
        default="ml/data/processed/master_merged_weather_seasonal.csv",
        help="Path to processed CSV"
    )
    parser.add_argument(
        "--table",
        default="agri_features",
        help="Destination table name"
    )
    parser.add_argument(
        "--if_exists",
        default="replace",
        choices=["replace", "append", "fail"],
        help="What to do if table exists"
    )
    parser.add_argument(
        "--chunksize",
        type=int,
        default=5000,
        help="Rows per insert batch (lower if RAM is low)"
    )
    args = parser.parse_args()

    csv_path = args.csv
    if not os.path.exists(csv_path):
        print(f"❌ CSV not found: {csv_path}")
        sys.exit(1)

    print(f"📥 Reading: {csv_path}")

    # Safer read for mixed dtype columns
    df = pd.read_csv(csv_path, low_memory=False)

    # Clean columns
    df.columns = [clean_col(c) for c in df.columns]

    # Cast types
    df = detect_and_cast(df)

    # Basic sanity checks
    print(f"✅ Rows: {len(df):,} | Cols: {len(df.columns)}")
    print("🔎 Example columns:", list(df.columns)[:15])

    engine = build_engine()

    print(f"🧠 Loading into PostgreSQL table: {args.table}")
    print(f"⚙️ if_exists={args.if_exists}, chunksize={args.chunksize}")

    # Write
    df.to_sql(
        name=args.table,
        con=engine,
        if_exists=args.if_exists,
        index=False,
        chunksize=args.chunksize,
        method="multi"
    )

    print("✅ Load complete!")

    # Verify counts
    with engine.connect() as conn:
        res = conn.execute(text(f"SELECT COUNT(*) FROM {args.table}"))
        count = res.scalar()
        print(f"📊 Rows in DB ({args.table}): {count:,}")

        if "arrival_date" in df.columns:
            res = conn.execute(text(f"SELECT MIN(arrival_date), MAX(arrival_date) FROM {args.table}"))
            mn, mx = res.fetchone()
            print(f"🗓️ arrival_date range: {mn} → {mx}")

        # # Try date range if arrival_date exists
        # if "arrival_date" in df.columns:
        #     res = conn.execute(f"SELECT MIN(arrival_date), MAX(arrival_date) FROM {args.table}")
        #     mn, mx = res.fetchone()
        #     print(f"🗓️ arrival_date range: {mn} → {mx}")

if __name__ == "__main__":
    main()