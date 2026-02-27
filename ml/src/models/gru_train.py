import os
import joblib
import numpy as np
import pandas as pd

from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

import tensorflow as tf
from tensorflow.keras import layers, callbacks, models

ART_DIR = "ml/artifacts/gru"
os.makedirs(ART_DIR, exist_ok=True)

TARGET = "modal_price"
DATE_COL = "arrival_date"

SEQ_LEN = 30
BATCH_SIZE = 256
EPOCHS = 30

# IMPORTANT: do NOT include raw categorical columns in GRU numeric scaler
DROP_ALWAYS = {
    DATE_COL, TARGET,
    "state","district","market","commodity_group","commodity","variety","grade",
    "price_unit","arrival_unit","season"
}

def mape(y_true, y_pred):
    y_true = np.array(y_true, dtype=float)
    y_pred = np.array(y_pred, dtype=float)
    denom = np.where(np.abs(y_true) < 1e-9, 1.0, np.abs(y_true))
    return np.mean(np.abs((y_true - y_pred) / denom)) * 100

def load_split(path):
    df = pd.read_csv(path, low_memory=False)
    df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")
    df[TARGET] = pd.to_numeric(df[TARGET], errors="coerce")
    df = df.dropna(subset=[DATE_COL, TARGET]).sort_values(DATE_COL)
    return df

def build_sequences(df, feature_cols, scaler=None, fit_scaler=False):
    df = df.copy()

    # sort by series
    key_cols = ["state", "market", "commodity"]
    df = df.sort_values(key_cols + [DATE_COL])

    # numeric cleanup
    df[feature_cols] = df[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)

    # scale X
    if fit_scaler:
        scaler = StandardScaler()
        scaler.fit(df[feature_cols].values)

    X_scaled = scaler.transform(df[feature_cols].values)
    df_scaled = df.reset_index(drop=True).copy()
    df_scaled[feature_cols] = X_scaled

    # log target (stabilizes)
    df_scaled["y_log"] = np.log1p(df_scaled[TARGET].values)

    X_list, y_list = [], []

    for _, g in df_scaled.groupby(key_cols):
        g = g.sort_values(DATE_COL)

        if len(g) <= SEQ_LEN:
            continue

        Xv = g[feature_cols].values
        yv = g["y_log"].values

        for i in range(SEQ_LEN, len(g)):
            X_list.append(Xv[i-SEQ_LEN:i])
            y_list.append(yv[i])

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.float32)

    return X, y, scaler

def build_model(n_features):
    model = models.Sequential([
        layers.Input(shape=(SEQ_LEN, n_features)),
        layers.GRU(64, return_sequences=True),
        layers.Dropout(0.2),
        layers.GRU(32),
        layers.Dropout(0.2),
        layers.Dense(32, activation="relu"),
        layers.Dense(1)
    ])
    model.compile(optimizer=tf.keras.optimizers.Adam(1e-3), loss="mse")
    return model

def report(split, y_log, pred_log):
    # convert back to price for metrics
    y = np.expm1(y_log)
    pred = np.expm1(pred_log)

    rmse = np.sqrt(mean_squared_error(y, pred))
    mae = mean_absolute_error(y, pred)
    _mape = mape(y, pred)
    r2 = r2_score(y, pred)

    print(f"{split} | RMSE={rmse:.3f} MAE={mae:.3f} MAPE={_mape:.2f}% R2={r2:.3f}")
    return {"split": split, "rmse": rmse, "mae": mae, "mape": _mape, "r2": r2}

def main():
    train = load_split("ml/data/processed/train.csv")
    val   = load_split("ml/data/processed/val.csv")
    test  = load_split("ml/data/processed/test.csv")

    # NUMERIC FEATURES ONLY
    feature_cols = [c for c in train.columns if c not in DROP_ALWAYS]

    # build sequences
    X_train, y_train, scaler = build_sequences(train, feature_cols, fit_scaler=True)
    X_val, y_val, _ = build_sequences(val, feature_cols, scaler=scaler, fit_scaler=False)
    X_test, y_test, _ = build_sequences(test, feature_cols, scaler=scaler, fit_scaler=False)

    print("✅ Sequences built")
    print("Train:", X_train.shape, "Val:", X_val.shape, "Test:", X_test.shape)

    model = build_model(n_features=X_train.shape[-1])

    cb = [
        callbacks.EarlyStopping(patience=5, restore_best_weights=True),
        callbacks.ReduceLROnPlateau(patience=3, factor=0.5, min_lr=1e-5)
    ]

    model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=EPOCHS,
        batch_size=BATCH_SIZE,
        verbose=1,
        callbacks=cb
    )

    pred_val = model.predict(X_val, verbose=0).reshape(-1)
    pred_test = model.predict(X_test, verbose=0).reshape(-1)

    metrics = []
    metrics.append(report("VAL", y_val, pred_val))
    metrics.append(report("TEST", y_test, pred_test))

    # save
    model.save(os.path.join(ART_DIR, "gru_model.keras"))
    joblib.dump(scaler, os.path.join(ART_DIR, "x_scaler.joblib"))
    joblib.dump(feature_cols, os.path.join(ART_DIR, "feature_cols.joblib"))
    pd.DataFrame(metrics).to_csv(os.path.join(ART_DIR, "metrics.csv"), index=False)

    print("✅ Saved GRU model + artifacts in:", ART_DIR)

if __name__ == "__main__":
    main()