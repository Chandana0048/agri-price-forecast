import os
import joblib
import numpy as np
import pandas as pd
import shap
import matplotlib.pyplot as plt

ART_DIR = "ml/artifacts"
DATA_DIR = "ml/data/processed"
OUT_DIR = "ml/artifacts/explainability"
os.makedirs(OUT_DIR, exist_ok=True)

TARGET = "modal_price"

def main():
    # -------------------------
    # Load model + test data
    # -------------------------
    model = joblib.load(os.path.join(ART_DIR, "xgb", "xgb_model.joblib"))
    test = pd.read_csv(os.path.join(DATA_DIR, "test.csv"), low_memory=False)

    # Feature columns (use saved if available)
    feat_path = os.path.join(ART_DIR, "xgb", "feature_cols.joblib")
    if os.path.exists(feat_path):
        feature_cols = joblib.load(feat_path)
    else:
        drop_cols = [TARGET, "arrival_date"]
        feature_cols = [c for c in test.columns if c not in drop_cols]

    X = test[feature_cols].copy()

    # Convert any object columns → numeric
    for c in X.columns:
        if X[c].dtype == "object":
            X[c] = pd.to_numeric(X[c], errors="coerce")
    X = X.fillna(0.0)

    # -------------------------
    # Sampling (8GB RAM friendly)
    # -------------------------
    # Background = used by SHAP masker
    bg_size = min(500, len(X))
    explain_size = min(1000, len(X))

    X_bg = X.sample(n=bg_size, random_state=42)
    X_explain = X.sample(n=explain_size, random_state=99)

    print("✅ Building SHAP explainer (model-agnostic, avoids TreeExplainer base_score bug)...")

    # -------------------------
    # Make model callable for SHAP
    # -------------------------
    # SHAP may pass numpy arrays, so we rebuild a DataFrame inside predict_fn
    def predict_fn(data):
        if isinstance(data, pd.DataFrame):
            return model.predict(data)
        data = np.array(data)
        df = pd.DataFrame(data, columns=feature_cols)
        return model.predict(df)

    masker = shap.maskers.Independent(X_bg)

    # permutation explainer = stable with any model
    explainer = shap.Explainer(
        predict_fn,
        masker=masker,
        feature_names=feature_cols,
        algorithm="permutation"
    )

    print("✅ Computing SHAP values (this can take a few minutes)...")
    shap_values = explainer(X_explain)

    # -------------------------
    # 1) Beeswarm summary
    # -------------------------
    plt.figure()
    shap.plots.beeswarm(shap_values, show=False)
    out1 = os.path.join(OUT_DIR, "xgb_shap_summary.png")
    plt.savefig(out1, dpi=200, bbox_inches="tight")
    plt.close()
    print("✅ Saved:", out1)

    # -------------------------
    # 2) Bar importance
    # -------------------------
    plt.figure()
    shap.plots.bar(shap_values, show=False)
    out2 = os.path.join(OUT_DIR, "xgb_shap_bar.png")
    plt.savefig(out2, dpi=200, bbox_inches="tight")
    plt.close()
    print("✅ Saved:", out2)

    # -------------------------
    # 3) Waterfall for one sample
    # -------------------------
    plt.figure()
    shap.plots.waterfall(shap_values[0], show=False)
    out3 = os.path.join(OUT_DIR, "xgb_shap_waterfall_one.png")
    plt.savefig(out3, dpi=200, bbox_inches="tight")
    plt.close()
    print("✅ Saved:", out3)

    print("\n✅ SHAP explainability completed successfully.")

if __name__ == "__main__":
    main()