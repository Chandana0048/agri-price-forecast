import os
import json
import joblib
import numpy as np
import pandas as pd

from lightgbm import LGBMRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

ART_DIR = "ml/artifacts/quantile"
DATA_DIR = "ml/data/processed"
os.makedirs(ART_DIR, exist_ok=True)

TARGET = "modal_price"

# These must NOT be fed as raw strings to the model
DROP_ALWAYS = [
    "arrival_date",
    "state", "district", "market",
    "commodity_group", "commodity", "variety", "grade",
    "price_unit", "arrival_unit", "season"
]

def mape(y_true, y_pred):
    y_true = np.array(y_true, dtype=float)
    y_pred = np.array(y_pred, dtype=float)
    denom = np.where(np.abs(y_true) < 1e-9, 1.0, np.abs(y_true))
    return np.mean(np.abs((y_true - y_pred) / denom)) * 100

def pinball_loss(y, yhat, q):
    y = np.array(y, dtype=float)
    yhat = np.array(yhat, dtype=float)
    diff = y - yhat
    return np.mean(np.maximum(q * diff, (q - 1) * diff))

def prep(df):
    df = df.copy()
    df[TARGET] = pd.to_numeric(df[TARGET], errors="coerce")
    df = df.dropna(subset=[TARGET])

    drop_cols = [c for c in DROP_ALWAYS if c in df.columns]
    X = df.drop(columns=drop_cols + [TARGET], errors="ignore")

    # force numeric
    for c in X.columns:
        if X[c].dtype == "object":
            X[c] = pd.to_numeric(X[c], errors="coerce")
    X = X.fillna(0.0)

    y = df[TARGET].astype(float).values
    return X, y, X.columns.tolist()

def train_quantile(X_train, y_train, X_val, y_val, alpha):
    model = LGBMRegressor(
        objective="quantile",
        alpha=alpha,
        n_estimators=1500,
        learning_rate=0.03,
        num_leaves=64,
        subsample=0.85,
        colsample_bytree=0.85,
        random_state=42,
        n_jobs=-1
    )
    model.fit(
        X_train, y_train,
        eval_set=[(X_val, y_val)],
        eval_metric="l2",
        callbacks=[],
    )
    return model

def main():
    train = pd.read_csv(os.path.join(DATA_DIR, "train.csv"), low_memory=False)
    val   = pd.read_csv(os.path.join(DATA_DIR, "val.csv"), low_memory=False)
    test  = pd.read_csv(os.path.join(DATA_DIR, "test.csv"), low_memory=False)

    Xtr, ytr, feat_cols = prep(train)
    Xva, yva, _ = prep(val)
    Xte, yte, _ = prep(test)

    # Save feature columns for deployment consistency
    joblib.dump(feat_cols, os.path.join(ART_DIR, "feature_cols.joblib"))

    print("Training Quantile models: q10, q50, q90")

    q10 = train_quantile(Xtr, ytr, Xva, yva, alpha=0.10)
    q50 = train_quantile(Xtr, ytr, Xva, yva, alpha=0.50)
    q90 = train_quantile(Xtr, ytr, Xva, yva, alpha=0.90)

    p10 = q10.predict(Xte)
    p50 = q50.predict(Xte)
    p90 = q90.predict(Xte)

    # enforce ordering (sometimes quantiles cross)
    lo = np.minimum(p10, p90)
    hi = np.maximum(p10, p90)
    med = p50

    coverage = np.mean((yte >= lo) & (yte <= hi)) * 100
    avg_width = np.mean(hi - lo)

    metrics = {
        "test_rmse_median": float(np.sqrt(mean_squared_error(yte, med))),
        "test_mae_median": float(mean_absolute_error(yte, med)),
        "test_mape_median": float(mape(yte, med)),
        "test_r2_median": float(r2_score(yte, med)),
        "pinball_q10": float(pinball_loss(yte, lo, 0.10)),
        "pinball_q50": float(pinball_loss(yte, med, 0.50)),
        "pinball_q90": float(pinball_loss(yte, hi, 0.90)),
        "interval_coverage_10_90_pct": float(coverage),
        "avg_interval_width": float(avg_width)
    }

    # Save artifacts
    joblib.dump(q10, os.path.join(ART_DIR, "lgbm_q10.joblib"))
    joblib.dump(q50, os.path.join(ART_DIR, "lgbm_q50.joblib"))
    joblib.dump(q90, os.path.join(ART_DIR, "lgbm_q90.joblib"))

    with open(os.path.join(ART_DIR, "metrics.json"), "w") as f:
        json.dump(metrics, f, indent=2)

    out = pd.DataFrame({
        "y_true": yte,
        "p10": lo,
        "p50": med,
        "p90": hi
    })
    out.to_csv(os.path.join(ART_DIR, "predictions_test.csv"), index=False)

    print("\n📌 PROBABILISTIC FORECAST (TEST)")
    for k, v in metrics.items():
        print(f"{k}: {v}")

    print("\n✅ Saved to:", ART_DIR)

if __name__ == "__main__":
    main()