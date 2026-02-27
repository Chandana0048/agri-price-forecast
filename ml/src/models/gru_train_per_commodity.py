import os
import joblib
import numpy as np
import pandas as pd

from sklearn.preprocessing import StandardScaler
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

import tensorflow as tf
from tensorflow.keras import layers, callbacks, models

ART_DIR = "ml/artifacts/gru_per_commodity"
os.makedirs(ART_DIR, exist_ok=True)

TARGET = "modal_price"
DATE_COL = "arrival_date"

SEQ_LEN = 30
BATCH_SIZE = 256
EPOCHS = 30

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
    df = df.sort_values([DATE_COL])

    df[feature_cols] = df[feature_cols].apply(pd.to_numeric, errors="coerce").fillna(0.0)

    if fit_scaler:
        scaler = StandardScaler()
        scaler.fit(df[feature_cols].values)

    X_scaled = scaler.transform(df[feature_cols].values)
    df2 = df.reset_index(drop=True).copy()
    df2[feature_cols] = X_scaled

    df2["y_log"] = np.log1p(df2[TARGET].values)

    X_list, y_list = [], []
    Xv = df2[feature_cols].values
    yv = df2["y_log"].values

    if len(df2) <= SEQ_LEN:
        return np.empty((0, SEQ_LEN, len(feature_cols))), np.empty((0,)), scaler

    for i in range(SEQ_LEN, len(df2)):
        X_list.append(Xv[i-SEQ_LEN:i])
        y_list.append(yv[i])

    X = np.array(X_list, dtype=np.float32)
    y = np.array(y_list, dtype=np.float32)
    return X, y, scaler

def build_model(n_features):
    model = models.Sequential([
        layers.Input(shape=(SEQ_LEN, n_features)),
        layers.GRU(64, return_sequences=True),
        layers.Dropout(0.25),
        layers.GRU(32),
        layers.Dropout(0.25),
        layers.Dense(32, activation="relu"),
        layers.Dense(1)
    ])
    model.compile(optimizer=tf.keras.optimizers.Adam(1e-3), loss="mse")
    return model

def report(split, y_log, pred_log):
    y = np.expm1(y_log)
    pred = np.expm1(pred_log)
    rmse = np.sqrt(mean_squared_error(y, pred))
    mae = mean_absolute_error(y, pred)
    _mape = mape(y, pred)
    r2 = r2_score(y, pred)
    print(f"{split} | RMSE={rmse:.3f} MAE={mae:.3f} MAPE={_mape:.2f}% R2={r2:.3f}")
    return rmse, mae, _mape, r2

def main():
    train = load_split("ml/data/processed/train.csv")
    val   = load_split("ml/data/processed/val.csv")
    test  = load_split("ml/data/processed/test.csv")

    commodities = sorted(train["commodity"].dropna().unique().tolist())
    print("Commodities:", commodities)

    for com in commodities:
        print("\n" + "="*70)
        print("Training GRU for commodity:", com)

        tr = train[train["commodity"] == com].copy()
        va = val[val["commodity"] == com].copy()
        te = test[test["commodity"] == com].copy()

        if len(tr) < 2000:
            print("⚠️ Skipping (too few rows):", len(tr))
            continue

        feature_cols = [c for c in tr.columns if c not in DROP_ALWAYS]

        X_train, y_train, scaler = build_sequences(tr, feature_cols, fit_scaler=True)
        X_val, y_val, _ = build_sequences(va, feature_cols, scaler=scaler, fit_scaler=False)
        X_test, y_test, _ = build_sequences(te, feature_cols, scaler=scaler, fit_scaler=False)

        print("Seq shapes:", X_train.shape, X_val.shape, X_test.shape)
        if X_train.shape[0] == 0 or X_val.shape[0] == 0 or X_test.shape[0] == 0:
            print("⚠️ Not enough sequences, skipping.")
            continue

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

        print("VAL metrics:")
        report("VAL", y_val, pred_val)
        print("TEST metrics:")
        report("TEST", y_test, pred_test)

        safe_name = com.lower().replace(" ", "_").replace("(", "").replace(")", "").replace("/", "_")
        out_dir = os.path.join(ART_DIR, safe_name)
        os.makedirs(out_dir, exist_ok=True)

        model.save(os.path.join(out_dir, "gru_model.keras"))
        joblib.dump(scaler, os.path.join(out_dir, "x_scaler.joblib"))
        joblib.dump(feature_cols, os.path.join(out_dir, "feature_cols.joblib"))

        print("✅ Saved:", out_dir)

if __name__ == "__main__":
    main()