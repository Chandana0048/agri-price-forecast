import os
import joblib
import numpy as np
import pandas as pd
from xgboost import XGBRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

ART_DIR = "ml/artifacts/xgb"
os.makedirs(ART_DIR, exist_ok=True)

TARGET = "modal_price"
DATE_COL = "arrival_date"

CAT_COLS = [
    "state", "district", "market", "commodity_group", "commodity",
    "variety", "grade", "price_unit", "arrival_unit", "season"
]

DROP_ALWAYS = [DATE_COL]


# ----------------------------
# Metrics
# ----------------------------
def mape(y_true, y_pred):
    y_true = np.array(y_true, dtype=float)
    y_pred = np.array(y_pred, dtype=float)
    denom = np.where(np.abs(y_true) < 1e-9, 1.0, np.abs(y_true))
    return np.mean(np.abs((y_true - y_pred) / denom)) * 100


def report(split, y, pred):
    rmse = np.sqrt(mean_squared_error(y, pred))
    mae = mean_absolute_error(y, pred)
    _mape = mape(y, pred)
    r2 = r2_score(y, pred)
    print(f"{split} | RMSE={rmse:.3f} MAE={mae:.3f} MAPE={_mape:.2f}% R2={r2:.3f}")
    return {"split": split, "rmse": rmse, "mae": mae, "mape": _mape, "r2": r2}


# ----------------------------
# Encoding helpers (TRAIN-FIT, REUSE)
# ----------------------------
def fit_cat_encoders(train_df: pd.DataFrame, cat_cols):
    encoders = {}
    for c in cat_cols:
        if c not in train_df.columns:
            encoders[c] = {"__UNK__": -1}
            continue
        # get unique string values from TRAIN ONLY
        vals = (
            train_df[c]
            .astype(str)
            .fillna("__UNK__")
            .unique()
            .tolist()
        )
        mapping = {v: i for i, v in enumerate(sorted(vals))}
        mapping["__UNK__"] = -1
        encoders[c] = mapping
    return encoders


def apply_cat_encoders(df: pd.DataFrame, encoders):
    df = df.copy()
    for c, mapping in encoders.items():
        if c not in df.columns:
            df[c] = -1
            continue
        s = df[c].astype(str).fillna("__UNK__")
        df[c] = s.map(mapping).fillna(-1).astype(int)
    return df


# ----------------------------
# Prep function
# ----------------------------
def prep(df: pd.DataFrame, encoders=None, feature_cols=None):
    df = df.copy()

    # Parse date
    if DATE_COL in df.columns:
        df[DATE_COL] = pd.to_datetime(df[DATE_COL], errors="coerce")

    # Target clean
    df[TARGET] = pd.to_numeric(df[TARGET], errors="coerce")
    df = df.dropna(subset=[TARGET])

    # Apply encoders if provided
    if encoders is not None:
        df = apply_cat_encoders(df, encoders)

    # Drop non-features
    drop_cols = [c for c in DROP_ALWAYS if c in df.columns]
    X = df.drop(columns=drop_cols + [TARGET], errors="ignore")

    # Enforce same feature columns (important!)
    if feature_cols is not None:
        # add missing cols with 0
        for c in feature_cols:
            if c not in X.columns:
                X[c] = 0
        # keep only training order
        X = X[feature_cols]

    # Ensure numeric
    for c in X.columns:
        if X[c].dtype == "object":
            X[c] = pd.to_numeric(X[c], errors="coerce")
    X = X.fillna(0.0)

    y = df[TARGET].astype(float).values
    return X, y


def main():
    train = pd.read_csv("ml/data/processed/train.csv", low_memory=False)
    val   = pd.read_csv("ml/data/processed/val.csv", low_memory=False)
    test  = pd.read_csv("ml/data/processed/test.csv", low_memory=False)

    # 1) Fit encoders ONLY on train
    encoders = fit_cat_encoders(train, CAT_COLS)

    # 2) Prep train first (get feature columns from train only)
    X_train, y_train = prep(train, encoders=encoders, feature_cols=None)
    feature_cols = list(X_train.columns)

    # 3) Prep val/test using SAME encoders and SAME columns
    X_val, y_val   = prep(val,  encoders=encoders, feature_cols=feature_cols)
    X_test, y_test = prep(test, encoders=encoders, feature_cols=feature_cols)

    model = XGBRegressor(
        n_estimators=1200,
        learning_rate=0.03,
        max_depth=8,
        subsample=0.8,
        colsample_bytree=0.8,
        reg_lambda=1.0,
        random_state=42,
        n_jobs=-1,
        tree_method="hist",
    )

    model.fit(X_train, y_train, eval_set=[(X_val, y_val)], verbose=False)

    pred_val  = model.predict(X_val)
    pred_test = model.predict(X_test)

    metrics = []
    metrics.append(report("VAL", y_val, pred_val))
    metrics.append(report("TEST", y_test, pred_test))

    # Save EVERYTHING needed for deployment
    joblib.dump(model, os.path.join(ART_DIR, "xgb_model.joblib"))
    joblib.dump(feature_cols, os.path.join(ART_DIR, "feature_cols.joblib"))
    joblib.dump(encoders, os.path.join(ART_DIR, "cat_encoders.joblib"))
    pd.DataFrame(metrics).to_csv(os.path.join(ART_DIR, "metrics.csv"), index=False)

    print("✅ Saved:")
    print(" -", os.path.join(ART_DIR, "xgb_model.joblib"))
    print(" -", os.path.join(ART_DIR, "feature_cols.joblib"))
    print(" -", os.path.join(ART_DIR, "cat_encoders.joblib"))
    print(" -", os.path.join(ART_DIR, "metrics.csv"))


if __name__ == "__main__":
    main()