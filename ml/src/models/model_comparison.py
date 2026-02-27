import os
import pandas as pd
import numpy as np
import joblib

from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

ART_DIR = "ml/artifacts"
DATA_DIR = "ml/data/processed"
TARGET = "modal_price"


def mape(y_true, y_pred):
    y_true = np.array(y_true, dtype=float)
    y_pred = np.array(y_pred, dtype=float)
    denom = np.where(np.abs(y_true) < 1e-9, 1.0, np.abs(y_true))
    return np.mean(np.abs((y_true - y_pred) / denom)) * 100


def compute_metrics(name, y_true, y_pred):
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    mp = float(mape(y_true, y_pred))
    r2 = float(r2_score(y_true, y_pred))
    return {"model": name, "rmse": rmse, "mae": mae, "mape": mp, "r2": r2}


# ----------------------------
# XGBOOST (recompute on test.csv)
# ----------------------------
def load_xgb_metrics():
    model_path = os.path.join(ART_DIR, "xgb", "xgb_model.joblib")
    if not os.path.exists(model_path):
        print("⚠️ XGBoost model not found:", model_path)
        return None

    model = joblib.load(model_path)
    test_path = os.path.join(DATA_DIR, "test.csv")
    test = pd.read_csv(test_path, low_memory=False)

    if TARGET not in test.columns:
        raise RuntimeError(f"Missing target column '{TARGET}' in {test_path}")

    y_true = pd.to_numeric(test[TARGET], errors="coerce").fillna(0).values

    feat_path = os.path.join(ART_DIR, "xgb", "feature_cols.joblib")
    if os.path.exists(feat_path):
        feature_cols = joblib.load(feat_path)
    else:
        booster = model.get_booster()
        feature_cols = booster.feature_names
        if not feature_cols:
            raise RuntimeError("XGBoost feature names missing. Save feature_cols.joblib in training.")

    missing = [c for c in feature_cols if c not in test.columns]
    if missing:
        raise RuntimeError(f"Test is missing XGBoost features: {missing[:15]} ...")

    X_test = test[feature_cols].copy()

    # ensure numeric
    for c in X_test.columns:
        if X_test[c].dtype == "object":
            X_test[c] = pd.to_numeric(X_test[c], errors="coerce")

    X_test = X_test.fillna(0.0)

    y_pred = model.predict(X_test)
    return compute_metrics("XGBoost", y_true, y_pred)


# ----------------------------
# GRU DELTA (read saved metrics.csv)
# ----------------------------
def load_gru_delta_metrics():
    path = os.path.join(ART_DIR, "gru_delta", "metrics.csv")
    if not os.path.exists(path):
        print("⚠️ GRU Delta metrics not found:", path)
        print("   Run your GRU delta training script that saves metrics.csv.")
        return None

    df = pd.read_csv(path)
    # Expect: model, split, rmse, mae, mape, r2
    # Keep TEST row
    if "split" in df.columns:
        df_test = df[df["split"].str.upper() == "TEST"].copy()
        if len(df_test) == 0:
            # If no split column or only one row, fallback to last row
            df_test = df.tail(1).copy()
    else:
        df_test = df.tail(1).copy()

    row = df_test.iloc[0].to_dict()
    # Normalize output keys
    return {
        "model": "GRU (Delta)",
        "rmse": float(row.get("rmse", np.nan)),
        "mae": float(row.get("mae", np.nan)),
        "mape": float(row.get("mape", np.nan)),
        "r2": float(row.get("r2", np.nan)),
    }


# ----------------------------
# SARIMAX (average over results)
# ----------------------------
def load_sarimax_metrics():
    path = os.path.join(ART_DIR, "sarimax", "sarimax_results.csv")
    if not os.path.exists(path):
        print("⚠️ SARIMAX results not found:", path)
        return None

    df = pd.read_csv(path)

    # tolerate different column names (your script used test_rmse etc.)
    col_map = {
        "test_rmse": "rmse",
        "test_mae": "mae",
        "test_mape": "mape",
        "test_r2": "r2"
    }
    for k in col_map:
        if k not in df.columns:
            raise RuntimeError(f"SARIMAX results missing column '{k}' in {path}")

    return {
        "model": "SARIMAX (avg)",
        "rmse": float(df["test_rmse"].mean()),
        "mae": float(df["test_mae"].mean()),
        "mape": float(df["test_mape"].mean()),
        "r2": float(df["test_r2"].mean()),
    }


def main():
    results = []

    print("Computing XGBoost metrics...")
    xgb = load_xgb_metrics()
    if xgb: results.append(xgb)

    print("Loading GRU (Delta) metrics...")
    gru = load_gru_delta_metrics()
    if gru: results.append(gru)

    print("Loading SARIMAX metrics...")
    sar = load_sarimax_metrics()
    if sar: results.append(sar)

    if not results:
        raise RuntimeError("No model metrics found. Train at least one model and save artifacts.")

    df_final = pd.DataFrame(results).sort_values("rmse", ascending=True)

    out_path = os.path.join(ART_DIR, "model_comparison.csv")
    df_final.to_csv(out_path, index=False)

    print("\n📊 FINAL MODEL COMPARISON (TEST)")
    print(df_final)
    print("\n✅ Saved to:", out_path)


if __name__ == "__main__":
    main()