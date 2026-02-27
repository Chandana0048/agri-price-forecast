import os
import joblib
import numpy as np
import pandas as pd

from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

import tensorflow as tf
from tensorflow.keras import layers, callbacks, models


# ----------------------------
# CONFIG
# ----------------------------
ART_DIR = "ml/artifacts/gru_delta"
os.makedirs(ART_DIR, exist_ok=True)

DATE_COL = "arrival_date"
TARGET = "modal_price"

SEQ_LEN = 30
BATCH = 256
EPOCHS = 30

# Columns never used as numeric features
DROP_ALWAYS = {
    DATE_COL, TARGET,
    "state", "district", "market", "commodity_group", "commodity", "variety", "grade",
    "price_unit", "arrival_unit", "season",
    # junk filename columns sometimes appear:
    "final_combined_data.xlsx",
    "daily_price_arrival_report_07_11_2025_to_19_02_2026_for_multiple_states_1_xlsx",
    "daily_price_arrival_report-07-11-2025_to_19-02-2026_for_multiple_states_(1).xlsx",
}

# For reproducibility (as much as TF allows on CPU)
SEED = 42
np.random.seed(SEED)
tf.random.set_seed(SEED)


# ----------------------------
# METRICS
# ----------------------------
def mape(y_true, y_pred):
    y_true = np.array(y_true, dtype=float)
    y_pred = np.array(y_pred, dtype=float)
    denom = np.where(np.abs(y_true) < 1e-9, 1.0, np.abs(y_true))
    return np.mean(np.abs((y_true - y_pred) / denom)) * 100


def compute_metrics(y_true, y_pred):
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    mp = float(mape(y_true, y_pred))
    r2 = float(r2_score(y_true, y_pred))
    return rmse, mae, mp, r2


def print_metrics(name, y_true, y_pred):
    rmse, mae, mp, r2 = compute_metrics(y_true, y_pred)
    print(f"{name} | RMSE={rmse:.3f} MAE={mae:.3f} MAPE={mp:.2f}% R2={r2:.3f}")
    return {"split": name, "rmse": rmse, "mae": mae, "mape": mp, "r2": r2}


# ----------------------------
# DATA LOAD
# ----------------------------
def load_split(path):
    df = pd.read_csv(path, low_memory=False)

    # normalize column names if needed
    df.columns = [c.strip() for c in df.columns]

    df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")
    df[TARGET] = pd.to_numeric(df[TARGET], errors="coerce")

    df = df.dropna(subset=[DATE_COL, TARGET]).sort_values(DATE_COL)
    return df


# ----------------------------
# MODEL
# ----------------------------
def build_model(n_features):
    m = models.Sequential([
        layers.Input(shape=(SEQ_LEN, n_features)),
        layers.GRU(64, return_sequences=True),
        layers.Dropout(0.25),
        layers.GRU(32),
        layers.Dropout(0.25),
        layers.Dense(32, activation="relu"),
        layers.Dense(1)  # delta(log price)
    ])
    m.compile(optimizer=tf.keras.optimizers.Adam(1e-3), loss="mse")
    return m


# ----------------------------
# SEQUENCE BUILDER (DELTA)
# ----------------------------
def build_sequences_delta(df, feature_cols, scaler=None, fit=False):
    df = df.copy()

    # we train per series identity
    key_cols = ["commodity", "state", "market"]
    for k in key_cols:
        if k not in df.columns:
            raise ValueError(f"Missing key column '{k}' in dataframe.")

    df = df.sort_values(key_cols + [DATE_COL])

    # ensure numeric features
    for c in feature_cols:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df[feature_cols] = df[feature_cols].fillna(0.0)

    # log price & delta target
    df["log_p"] = np.log1p(df[TARGET].values)
    df["log_p_lag1"] = df.groupby(key_cols)["log_p"].shift(1)
    df["delta"] = df["log_p"] - df["log_p_lag1"]

    df = df.dropna(subset=["log_p_lag1", "delta"]).reset_index(drop=True)

    # fit scaler on TRAIN ONLY
    if fit:
        scaler = StandardScaler()
        scaler.fit(df[feature_cols].values)

    if scaler is None:
        raise ValueError("Scaler is None. Pass scaler or set fit=True.")

    X_scaled = scaler.transform(df[feature_cols].values)
    df.loc[:, feature_cols] = X_scaled

    X_list, y_list, prev_log_list = [], [], []

    for _, g in df.groupby(key_cols, sort=False):
        g = g.sort_values(DATE_COL)
        if len(g) <= SEQ_LEN:
            continue

        Xv = g[feature_cols].values
        yv = g["delta"].values
        prev = g["log_p_lag1"].values

        for i in range(SEQ_LEN, len(g)):
            X_list.append(Xv[i-SEQ_LEN:i])
            y_list.append(yv[i])
            prev_log_list.append(prev[i])

    if not X_list:
        return (
            np.empty((0, SEQ_LEN, len(feature_cols)), dtype=np.float32),
            np.empty((0,), dtype=np.float32),
            np.empty((0,), dtype=np.float32),
            scaler
        )

    return (
        np.array(X_list, dtype=np.float32),
        np.array(y_list, dtype=np.float32),
        np.array(prev_log_list, dtype=np.float32),
        scaler
    )


# ----------------------------
# MAIN
# ----------------------------
def main():
    train = load_split("ml/data/processed/train.csv")
    val   = load_split("ml/data/processed/val.csv")
    test  = load_split("ml/data/processed/test.csv")

    # choose feature columns from TRAIN only
    feature_cols = [c for c in train.columns if c not in DROP_ALWAYS]

    # also drop any object columns that slipped in (safety)
    feature_cols = [c for c in feature_cols if pd.api.types.is_numeric_dtype(train[c])]

    Xtr, ytr, prev_tr, scaler = build_sequences_delta(train, feature_cols, fit=True)
    Xva, yva, prev_va, _ = build_sequences_delta(val, feature_cols, scaler=scaler, fit=False)
    Xte, yte, prev_te, _ = build_sequences_delta(test, feature_cols, scaler=scaler, fit=False)

    if Xtr.shape[0] == 0 or Xva.shape[0] == 0 or Xte.shape[0] == 0:
        raise RuntimeError(
            f"Not enough sequences built. "
            f"Train={Xtr.shape}, Val={Xva.shape}, Test={Xte.shape}"
        )

    print("✅ Sequences built")
    print("Train:", Xtr.shape, "Val:", Xva.shape, "Test:", Xte.shape)

    model = build_model(Xtr.shape[-1])

    cb = [
        callbacks.EarlyStopping(patience=5, restore_best_weights=True),
        callbacks.ReduceLROnPlateau(patience=3, factor=0.5, min_lr=1e-5),
    ]

    model.fit(
        Xtr, ytr,
        validation_data=(Xva, yva),
        epochs=EPOCHS,
        batch_size=BATCH,
        verbose=1,
        callbacks=cb
    )

    # predict deltas
    pred_va_delta = model.predict(Xva, verbose=0).reshape(-1)
    pred_te_delta = model.predict(Xte, verbose=0).reshape(-1)

    # reconstruct log price: log_p = prev_log + delta
    pred_va_logp = prev_va + pred_va_delta
    pred_te_logp = prev_te + pred_te_delta

    # true log price for each sample
    true_va_logp = prev_va + yva
    true_te_logp = prev_te + yte

    # back to price space
    y_va = np.expm1(true_va_logp)
    y_te = np.expm1(true_te_logp)
    p_va = np.expm1(pred_va_logp)
    p_te = np.expm1(pred_te_logp)

    print("VAL metrics:")
    val_row = print_metrics("VAL", y_va, p_va)
    print("TEST metrics:")
    test_row = print_metrics("TEST", y_te, p_te)

    # save model artifacts
    model.save(os.path.join(ART_DIR, "gru_delta.keras"))
    joblib.dump(scaler, os.path.join(ART_DIR, "x_scaler.joblib"))
    joblib.dump(feature_cols, os.path.join(ART_DIR, "feature_cols.joblib"))

    # ✅ SAVE METRICS CSV (this is what your comparison script needs)
    metrics_df = pd.DataFrame([
        {"model": "GRU (Delta)", **val_row},
        {"model": "GRU (Delta)", **test_row},
    ])
    metrics_path = os.path.join(ART_DIR, "metrics.csv")
    metrics_df.to_csv(metrics_path, index=False)

    print("✅ Saved:", ART_DIR)
    print("✅ Saved metrics:", metrics_path)


if __name__ == "__main__":
    main()