import os
import json
import joblib
import optuna
import numpy as np
import pandas as pd

from lightgbm import LGBMRegressor
from sklearn.metrics import mean_squared_error, mean_absolute_error, r2_score

DATA_DIR = "ml/data/processed"
ART_OUT = "ml/artifacts/ensemble"
os.makedirs(ART_OUT, exist_ok=True)

def mape(y_true, y_pred):
    y_true = np.array(y_true, dtype=float)
    y_pred = np.array(y_pred, dtype=float)
    denom = np.where(np.abs(y_true) < 1e-9, 1.0, np.abs(y_true))
    return np.mean(np.abs((y_true - y_pred) / denom)) * 100

def metrics(y_true, y_pred):
    rmse = float(np.sqrt(mean_squared_error(y_true, y_pred)))
    mae = float(mean_absolute_error(y_true, y_pred))
    mp = float(mape(y_true, y_pred))
    r2 = float(r2_score(y_true, y_pred))
    return rmse, mae, mp, r2

def main():
    val_path = os.path.join(DATA_DIR, "meta_val.csv")
    test_path = os.path.join(DATA_DIR, "meta_test.csv")

    if not os.path.exists(val_path) or not os.path.exists(test_path):
        raise FileNotFoundError("Run stacking_features.py first to generate meta_val/meta_test")

    val = pd.read_csv(val_path)
    test = pd.read_csv(test_path)

    val["arrival_date"] = pd.to_datetime(val["arrival_date"], errors="coerce")
    test["arrival_date"] = pd.to_datetime(test["arrival_date"], errors="coerce")

    val = val.sort_values("arrival_date").reset_index(drop=True)
    test = test.sort_values("arrival_date").reset_index(drop=True)

    y_val = val["y_true"].astype(float).values
    y_test = test["y_true"].astype(float).values

    feature_cols = [c for c in val.columns if c not in ["arrival_date", "y_true"]]
    X_val = val[feature_cols].copy()
    X_test = test[feature_cols].copy()

    # internal time split inside meta_val for Optuna
    n = len(val)
    cut = int(n * 0.8)  # first 80% train, last 20% eval
    X_tr, y_tr = X_val.iloc[:cut], y_val[:cut]
    X_ev, y_ev = X_val.iloc[cut:], y_val[cut:]

    def objective(trial):
        params = {
            "n_estimators": trial.suggest_int("n_estimators", 300, 2000),
            "learning_rate": trial.suggest_float("learning_rate", 0.005, 0.2, log=True),
            "max_depth": trial.suggest_int("max_depth", 3, 12),
            "num_leaves": trial.suggest_int("num_leaves", 16, 256),
            "min_child_samples": trial.suggest_int("min_child_samples", 10, 200),
            "subsample": trial.suggest_float("subsample", 0.6, 1.0),
            "colsample_bytree": trial.suggest_float("colsample_bytree", 0.6, 1.0),
            "reg_alpha": trial.suggest_float("reg_alpha", 0.0, 5.0),
            "reg_lambda": trial.suggest_float("reg_lambda", 0.0, 10.0),
            "random_state": 42,
            "n_jobs": -1,
        }

        model = LGBMRegressor(**params)
        model.fit(X_tr, y_tr)

        pred = model.predict(X_ev)
        rmse = np.sqrt(mean_squared_error(y_ev, pred))
        return rmse

    print("🧪 Optuna tuning LightGBM meta-model...")
    study = optuna.create_study(direction="minimize")
    study.optimize(objective, n_trials=30)  # keep 30 for your 8GB laptop

    best_params = study.best_params
    best_params.update({"random_state": 42, "n_jobs": -1})

    print("✅ Best params:", best_params)

    # Train final meta-model on all meta_val
    meta_model = LGBMRegressor(**best_params)
    meta_model.fit(X_val, y_val)

    pred_test = meta_model.predict(X_test)

    rmse, mae, mp, r2 = metrics(y_test, pred_test)

    print("\n📌 ENSEMBLE (LightGBM meta) TEST METRICS")
    print(f"TEST | RMSE={rmse:.3f} MAE={mae:.3f} MAPE={mp:.2f}% R2={r2:.3f}")

    # Save artifacts
    joblib.dump(meta_model, os.path.join(ART_OUT, "lgbm_meta.joblib"))
    with open(os.path.join(ART_OUT, "best_params.json"), "w") as f:
        json.dump(best_params, f, indent=2)

    pd.DataFrame([{
        "model": "LightGBM_meta",
        "rmse": rmse,
        "mae": mae,
        "mape": mp,
        "r2": r2,
        "features_used": len(feature_cols)
    }]).to_csv(os.path.join(ART_OUT, "metrics.csv"), index=False)

    print("\n✅ Saved:")
    print(" - ml/artifacts/ensemble/lgbm_meta.joblib")
    print(" - ml/artifacts/ensemble/best_params.json")
    print(" - ml/artifacts/ensemble/metrics.csv")

if __name__ == "__main__":
    main()