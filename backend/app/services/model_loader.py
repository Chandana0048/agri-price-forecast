import os
import joblib

# project root = go up from backend/app/services -> backend/app -> backend -> project_root
BASE_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
ML_ART_DIR = os.path.join(BASE_DIR, "ml", "artifacts")

def load_quantile_models():
    qdir = os.path.join(ML_ART_DIR, "quantile")

    paths = {
        "q10": os.path.join(qdir, "lgbm_q10.joblib"),
        "q50": os.path.join(qdir, "lgbm_q50.joblib"),
        "q90": os.path.join(qdir, "lgbm_q90.joblib"),
        "feature_cols": os.path.join(qdir, "feature_cols.joblib"),
    }

    missing = [k for k, p in paths.items() if not os.path.exists(p)]
    if missing:
        raise FileNotFoundError(f"Missing quantile artifacts: {missing} in {qdir}")

    models = {
        "q10": joblib.load(paths["q10"]),
        "q50": joblib.load(paths["q50"]),
        "q90": joblib.load(paths["q90"]),
        "feature_cols": joblib.load(paths["feature_cols"]),
    }
    return models