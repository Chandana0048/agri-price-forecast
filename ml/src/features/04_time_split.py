# import os
# import pandas as pd

# IN_FILE = os.path.join("ml", "data", "processed", "master_features.csv")
# OUT_DIR = os.path.join("ml", "data", "processed")

# def main():
#     df = pd.read_csv(IN_FILE, low_memory=False)
#     df.columns = [c.strip().lower().replace(" ", "_") for c in df.columns]
#     df["arrival_date"] = pd.to_datetime(df["arrival_date"], errors="coerce")
#     df = df.dropna(subset=["arrival_date"]).sort_values("arrival_date")

#     # global time split (simple + prevents leakage)
#     dates = df["arrival_date"].sort_values().unique()
#     n = len(dates)

#     train_end = dates[int(n * 0.70)]
#     val_end   = dates[int(n * 0.85)]

#     train = df[df["arrival_date"] <= train_end]
#     val   = df[(df["arrival_date"] > train_end) & (df["arrival_date"] <= val_end)]
#     test  = df[df["arrival_date"] > val_end]

#     train.to_csv(os.path.join(OUT_DIR, "train.csv"), index=False)
#     val.to_csv(os.path.join(OUT_DIR, "val.csv"), index=False)
#     test.to_csv(os.path.join(OUT_DIR, "test.csv"), index=False)

#     print("✅ Split done:")
#     print("Train:", len(train), "Val:", len(val), "Test:", len(test))
#     print("Train end:", train_end, "| Val end:", val_end)

# if __name__ == "__main__":
#     main()





import os
import pandas as pd

IN_FILE = "ml/data/processed/master_clean.csv"
OUT_DIR = "ml/data/processed"

TRAIN_FRAC = 0.70
VAL_FRAC   = 0.15
TEST_FRAC  = 0.15

DATE_COL = "arrival_date"

def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    df = pd.read_csv(IN_FILE, low_memory=False)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")
    df = df.dropna(subset=[DATE_COL]).sort_values(DATE_COL).reset_index(drop=True)

    n = len(df)
    n_train = int(n * TRAIN_FRAC)
    n_val   = int(n * (TRAIN_FRAC + VAL_FRAC))

    train = df.iloc[:n_train].copy()
    val   = df.iloc[n_train:n_val].copy()
    test  = df.iloc[n_val:].copy()

    train.to_csv(os.path.join(OUT_DIR, "train.csv"), index=False)
    val.to_csv(os.path.join(OUT_DIR, "val.csv"), index=False)
    test.to_csv(os.path.join(OUT_DIR, "test.csv"), index=False)

    print("✅ Split done")
    print("Train:", len(train), train[DATE_COL].min(), "→", train[DATE_COL].max())
    print("Val  :", len(val),   val[DATE_COL].min(),   "→", val[DATE_COL].max())
    print("Test :", len(test),  test[DATE_COL].min(),  "→", test[DATE_COL].max())

if __name__ == "__main__":
    main()