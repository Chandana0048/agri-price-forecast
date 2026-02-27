import os
import pandas as pd
import matplotlib.pyplot as plt

IN_FILE = os.path.join("ml", "data", "processed", "master_clean.csv")
OUT_DIR = os.path.join("ml", "eda")
os.makedirs(OUT_DIR, exist_ok=True)

def main():
    df = pd.read_csv(IN_FILE, low_memory=False)
    df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
    df["arrival_date"] = pd.to_datetime(df["arrival_date"], errors="coerce")
    df = df.dropna(subset=["arrival_date"])

    # 1) records per commodity
    c = df["commodity"].value_counts()
    plt.figure()
    c.plot(kind="bar")
    plt.title("Records per Commodity")
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, "records_per_commodity.png"))
    plt.close()

    # 2) price trend example (top commodity)
    top_com = c.index[0]
    d2 = df[df["commodity"] == top_com].sort_values("arrival_date")
    daily = d2.groupby("arrival_date")["modal_price"].mean()

    plt.figure()
    daily.plot()
    plt.title(f"Average Modal Price Trend: {top_com}")
    plt.tight_layout()
    plt.savefig(os.path.join(OUT_DIR, f"price_trend_{top_com}.png"))
    plt.close()

    print("✅ EDA plots saved in:", OUT_DIR)

if __name__ == "__main__":
    main()