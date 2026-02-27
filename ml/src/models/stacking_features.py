import os
import json
import joblib
import numpy as np
import pandas as pd

import tensorflow as tf
from sklearn.preprocessing import StandardScaler

ART_DIR = "ml/artifacts"
DATA_DIR = "ml/data/processed"
OUT_DIR = "ml/data/processed"

DATE_COL = "arrival_date"
TARGET = "modal_price"

# GRU-Delta settings
SEQ_LEN = 30
KEY_COLS = ["commodity", "state", "market"]  # identity per time-series


# ----------------------------
# Utils
# ----------------------------
def ensure_datetime(df: pd.DataFrame) -> pd.DataFrame:
    df = df.copy()
    df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")
    df[TARGET] = pd.to_numeric(df[TARGET], errors="coerce")
    df = df.dropna(subset=[DATE_COL, TARGET]).sort_values(DATE_COL).reset_index(drop=True)
    return df


def safe_to_numeric(df: pd.DataFrame, cols):
    for c in cols:
        if c in df.columns and df[c].dtype == "object":
            df[c] = pd.to_numeric(df[c], errors="coerce")
    return df


def load_split(name: str) -> pd.DataFrame:
    path = os.path.join(DATA_DIR, f"{name}.csv")
    if not os.path.exists(path):
        raise FileNotFoundError(f"Missing: {path}")
    df = pd.read_csv(path, low_memory=False)
    return ensure_datetime(df)


# ----------------------------
# XGBoost prediction
# ----------------------------
def apply_cat_encoders(df: pd.DataFrame, encoders: dict, cat_cols: list) -> pd.DataFrame:
    """
    encoders expected format:
    {col: {"categories": [...]} } OR {col: [...]} (list of categories)
    Unknown -> -1
    """
    out = df.copy()
    for c in cat_cols:
        if c not in out.columns:
            out[c] = -1
            continue

        raw = out[c].astype(str)

        if c in encoders:
            cats = encoders[c]
            if isinstance(cats, dict) and "categories" in cats:
                cats = cats["categories"]

            mapping = {str(v): i for i, v in enumerate(list(cats))}
            out[c] = raw.map(mapping).fillna(-1).astype(int)
        else:
            # fallback: simple category codes (NOT perfect, but prevents crashes)
            out[c] = raw.astype("category").cat.codes.astype(int)

    return out


def predict_xgb(df: pd.DataFrame) -> np.ndarray:
    model = joblib.load(os.path.join(ART_DIR, "xgb", "xgb_model.joblib"))
    feat_cols = joblib.load(os.path.join(ART_DIR, "xgb", "feature_cols.joblib"))

    enc_path = os.path.join(ART_DIR, "xgb", "cat_encoders.joblib")
    cat_cols = ["state", "district", "market", "commodity_group", "commodity", "variety", "grade", "price_unit", "arrival_unit", "season"]

    X = df.copy()
    if os.path.exists(enc_path):
        encoders = joblib.load(enc_path)
        X = apply_cat_encoders(X, encoders, cat_cols)
    else:
        # still encode to avoid object dtype
        X = apply_cat_encoders(X, {}, cat_cols)

    # Keep only trained columns
    X = X[feat_cols].copy()

    # Ensure numeric
    for c in X.columns:
        if X[c].dtype == "object":
            X[c] = pd.to_numeric(X[c], errors="coerce")
    X = X.fillna(0.0)

    pred = model.predict(X)
    return pred


# ----------------------------
# GRU-Delta prediction (sequence-based)
# ----------------------------
def build_sequences_delta_with_index(df: pd.DataFrame, feature_cols: list, scaler: StandardScaler):
    """
    Builds GRU-Delta sequences and returns:
    X_seq, prev_log, row_idx (index in df for the predicted point)
    """
    df = df.copy()
    df = df.sort_values(KEY_COLS + [DATE_COL]).reset_index(drop=True)

    # Ensure numeric features
    for c in feature_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df[feature_cols] = df[feature_cols].fillna(0.0)

    # log price and delta
    df["log_p"] = np.log1p(df[TARGET].values)
    df["log_p_lag1"] = df.groupby(KEY_COLS)["log_p"].shift(1)
    df["delta"] = df["log_p"] - df["log_p_lag1"]

    df = df.dropna(subset=["log_p_lag1", "delta"]).reset_index(drop=True)

    X_scaled = scaler.transform(df[feature_cols].values)
    df[feature_cols] = X_scaled

    X_list, prev_list, idx_list = [], [], []

    for _, g in df.groupby(KEY_COLS):
        g = g.sort_values(DATE_COL)
        if len(g) <= SEQ_LEN:
            continue

        Xv = g[feature_cols].values
        prev = g["log_p_lag1"].values
        # original row position in this filtered df
        g_idx = g.index.values

        for i in range(SEQ_LEN, len(g)):
            X_list.append(Xv[i - SEQ_LEN:i])
            prev_list.append(prev[i])
            idx_list.append(g_idx[i])

    if not X_list:
        return np.empty((0, SEQ_LEN, len(feature_cols))), np.empty((0,)), np.empty((0,), dtype=int)

    return (
        np.array(X_list, dtype=np.float32),
        np.array(prev_list, dtype=np.float32),
        np.array(idx_list, dtype=int),
    )


def predict_gru_delta_on_target_split(train_df, target_df, split_name: str):
    """
    To predict on VAL, we need history from TRAIN.
    To predict on TEST, we need history from TRAIN+VAL.
    We'll concatenate, build sequences, and then pick rows belonging to target_df dates.
    """
    model = tf.keras.models.load_model(os.path.join(ART_DIR, "gru_delta", "gru_delta.keras"))
    scaler = joblib.load(os.path.join(ART_DIR, "gru_delta", "x_scaler.joblib"))
    feature_cols = joblib.load(os.path.join(ART_DIR, "gru_delta", "feature_cols.joblib"))

    # Build a combined frame to provide history
    combined = pd.concat([train_df, target_df], ignore_index=True)
    combined = ensure_datetime(combined)

    # Build sequences on combined
    Xseq, prev_log, idx_list = build_sequences_delta_with_index(combined, feature_cols, scaler=scaler)

    if len(idx_list) == 0:
        # nothing available
        out = target_df.copy()
        out["gru_delta_pred"] = np.nan
        return out

    pred_delta = model.predict(Xseq, verbose=0).reshape(-1)
    pred_logp = prev_log + pred_delta
    pred_price = np.expm1(pred_logp)

    # We need to map combined-row indices -> prediction
    pred_map = {int(i): float(p) for i, p in zip(idx_list, pred_price)}

    # Now assign predictions back to combined
    combined["gru_delta_pred"] = [pred_map.get(i, np.nan) for i in range(len(combined))]

    # Return only rows corresponding to the *target_df portion* (the tail)
    out = combined.iloc[len(train_df):].copy()
    out = out.reset_index(drop=True)

    # Diagnostics
    available = out["gru_delta_pred"].notna().mean() * 100
    print(f"✅ GRU-Delta coverage for {split_name}: {available:.2f}% rows have GRU prediction")

    return out


# ----------------------------
# Build meta datasets
# ----------------------------
def make_meta(df: pd.DataFrame, split_name: str) -> pd.DataFrame:
    """
    Keep only clean numeric meta-features:
    - base preds (xgb_pred, gru_delta_pred)
    - indicator (has_gru)
    - a small set of numeric context features to help the meta model
    """
    keep_numeric_candidates = [
        "t2m", "t2m_max", "t2m_min", "prectotcorr", "rh2m", "ws2m",
        "arrival_quantity", "market_freq",
        "month", "weekofyear", "day_of_week", "quarter", "is_weekend",
        "modal_lag_1", "modal_lag_3", "modal_lag_7", "modal_roll_7", "modal_roll_14",
        "modal_vol_7", "temp_range", "temp_x_humidity", "rain_lag_1"
    ]

    meta = pd.DataFrame()
    meta["arrival_date"] = df[DATE_COL]
    meta["y_true"] = df[TARGET].astype(float)

    meta["xgb_pred"] = df["xgb_pred"].astype(float)
    meta["gru_delta_pred"] = df["gru_delta_pred"].astype(float)
    meta["has_gru"] = meta["gru_delta_pred"].notna().astype(int)

    # fill GRU missing with XGB (so meta model always has a value)
    meta["gru_delta_pred"] = meta["gru_delta_pred"].fillna(meta["xgb_pred"])

    # add numeric context features (only if present)
    for c in keep_numeric_candidates:
        if c in df.columns:
            meta[c] = pd.to_numeric(df[c], errors="coerce").fillna(0.0)

    # final cleanup
    meta = meta.sort_values("arrival_date").reset_index(drop=True)

    out_path = os.path.join(OUT_DIR, f"meta_{split_name}.csv")
    meta.to_csv(out_path, index=False)
    print(f"✅ Saved meta features: {out_path} | rows={len(meta):,} cols={len(meta.columns)}")
    return meta


def main():
    os.makedirs(OUT_DIR, exist_ok=True)

    train = load_split("train")
    val = load_split("val")
    test = load_split("test")

    # ---- XGB preds (all rows) ----
    print("🔮 Predicting XGBoost for VAL/TEST...")
    val["xgb_pred"] = predict_xgb(val)
    test["xgb_pred"] = predict_xgb(test)

    # ---- GRU-Delta preds (sequence based + needs history) ----
    print("🔮 Predicting GRU-Delta for VAL (with TRAIN history)...")
    val_with_gru = predict_gru_delta_on_target_split(train, val, "val")

    print("🔮 Predicting GRU-Delta for TEST (with TRAIN+VAL history)...")
    train_val = pd.concat([train, val], ignore_index=True)
    test_with_gru = predict_gru_delta_on_target_split(train_val, test, "test")

    # We already computed xgb_pred on original val/test; attach safely
    val_with_gru["xgb_pred"] = val["xgb_pred"].values
    test_with_gru["xgb_pred"] = test["xgb_pred"].values

    # ---- Build meta datasets ----
    make_meta(val_with_gru, "val")
    make_meta(test_with_gru, "test")

    print("\n✅ Stacking meta datasets ready.")
    print("Next: train LightGBM meta-model with Optuna.")


if __name__ == "__main__":
    main()