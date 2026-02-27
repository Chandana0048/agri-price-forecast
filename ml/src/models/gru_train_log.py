import os
import numpy as np
import pandas as pd
from pathlib import Path

from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

import tensorflow as tf
from tensorflow.keras import layers, callbacks, models

BASE_DIR = Path("ml")
DATA_DIR = BASE_DIR / "data" / "processed"
ART_DIR = BASE_DIR / "artifacts" / "gru_log"
ART_DIR.mkdir(parents=True, exist_ok=True)

TRAIN_FILE = DATA_DIR / "train.csv"
VAL_FILE   = DATA_DIR / "val.csv"
TEST_FILE  = DATA_DIR / "test.csv"

TARGET_COL = "modal_price"
DATE_COL = "arrival_date"

SEQ_LEN = 30
BATCH = 64
EPOCHS = 30

# ---- helpers ----
def mape(y_true, y_pred):
    y_true = np.array(y_true)
    y_pred = np.array(y_pred)
    denom = np.maximum(np.abs(y_true), 1e-6)
    return np.mean(np.abs((y_true - y_pred) / denom)) * 100

def build_sequences(X, y, seq_len):
    Xs, ys = [], []
    for i in range(seq_len, len(X)):
        Xs.append(X[i-seq_len:i])
        ys.append(y[i])
    return np.array(Xs), np.array(ys)

def main():
    print("📥 Loading splits...")
    train = pd.read_csv(TRAIN_FILE, low_memory=False)
    val   = pd.read_csv(VAL_FILE, low_memory=False)
    test  = pd.read_csv(TEST_FILE, low_memory=False)

    # sort by date to keep sequence order
    for df in (train, val, test):
        df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")
        df.sort_values([DATE_COL], inplace=True)

    # Drop non-numeric/object columns for GRU input
    # We'll keep only numeric features + engineered features already made
    drop_cols = [TARGET_COL, DATE_COL]
    X_train = train.drop(columns=[c for c in drop_cols if c in train.columns], errors="ignore")
    X_val   = val.drop(columns=[c for c in drop_cols if c in val.columns], errors="ignore")
    X_test  = test.drop(columns=[c for c in drop_cols if c in test.columns], errors="ignore")

    # Keep only numeric
    X_train = X_train.select_dtypes(include=[np.number]).fillna(0)
    X_val   = X_val.select_dtypes(include=[np.number]).fillna(0)
    X_test  = X_test.select_dtypes(include=[np.number]).fillna(0)

    feature_cols = list(X_train.columns)

    # log target
    y_train = np.log1p(pd.to_numeric(train[TARGET_COL], errors="coerce").fillna(0).values)
    y_val   = np.log1p(pd.to_numeric(val[TARGET_COL], errors="coerce").fillna(0).values)
    y_test  = np.log1p(pd.to_numeric(test[TARGET_COL], errors="coerce").fillna(0).values)

    # scale X
    x_scaler = StandardScaler()
    X_train_s = x_scaler.fit_transform(X_train)
    X_val_s   = x_scaler.transform(X_val)
    X_test_s  = x_scaler.transform(X_test)

    # build sequences
    Xtr, ytr = build_sequences(X_train_s, y_train, SEQ_LEN)
    Xva, yva = build_sequences(X_val_s, y_val, SEQ_LEN)
    Xte, yte = build_sequences(X_test_s, y_test, SEQ_LEN)

    print("✅ Sequences built")
    print("Train:", Xtr.shape, "Val:", Xva.shape, "Test:", Xte.shape)

    # model
    model = models.Sequential([
        layers.Input(shape=(SEQ_LEN, Xtr.shape[-1])),
        layers.GRU(64, return_sequences=True),
        layers.Dropout(0.2),
        layers.GRU(32),
        layers.Dense(16, activation="relu"),
        layers.Dense(1)
    ])

    model.compile(optimizer=tf.keras.optimizers.Adam(1e-3), loss="mse")

    cb = [
        callbacks.EarlyStopping(patience=5, restore_best_weights=True),
        callbacks.ReduceLROnPlateau(patience=2, factor=0.5, verbose=1),
    ]

    history = model.fit(
        Xtr, ytr,
        validation_data=(Xva, yva),
        epochs=EPOCHS,
        batch_size=BATCH,
        callbacks=cb,
        verbose=1
    )

    # predict and invert log
    yva_pred_log = model.predict(Xva).reshape(-1)
    yte_pred_log = model.predict(Xte).reshape(-1)

    yva_pred = np.expm1(yva_pred_log)
    yte_pred = np.expm1(yte_pred_log)

    yva_true = np.expm1(yva)
    yte_true = np.expm1(yte)

    def metrics(name, yt, yp):
        rmse = np.sqrt(mean_squared_error(yt, yp))
        mae  = mean_absolute_error(yt, yp)
        mp   = mape(yt, yp)
        r2   = r2_score(yt, yp)
        print(f"{name} | RMSE={rmse:.3f} MAE={mae:.3f} MAPE={mp:.2f}% R2={r2:.3f}")
        return rmse, mae, mp, r2

    val_m = metrics("VAL", yva_true, yva_pred)
    test_m = metrics("TEST", yte_true, yte_pred)

    # save artifacts
    model.save(ART_DIR / "gru_log.keras")
    import joblib
    joblib.dump(x_scaler, ART_DIR / "x_scaler.joblib")
    joblib.dump(feature_cols, ART_DIR / "feature_cols.joblib")

    metrics_df = pd.DataFrame([{
        "model": "GRU (log price)",
        "rmse": val_m[0],
        "mae": val_m[1],
        "mape": val_m[2],
        "r2": val_m[3],
        "split": "val"
    },{
        "model": "GRU (log price)",
        "rmse": test_m[0],
        "mae": test_m[1],
        "mape": test_m[2],
        "r2": test_m[3],
        "split": "test"
    }])
    metrics_df.to_csv(ART_DIR / "metrics.csv", index=False)

    print(f"✅ Saved GRU(log) model + metrics in: {ART_DIR}")

if __name__ == "__main__":
    main()