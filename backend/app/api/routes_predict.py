from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional
import numpy as np

from backend.app.services.model_loader import load_quantile_models
from backend.app.services.feature_builder import build_features

router = APIRouter()
Q = load_quantile_models()

class PredictRequest(BaseModel):
    state: str
    market: str
    commodity: str
    arrival_date: str  # YYYY-MM-DD
    district: Optional[str] = None

@router.get("/health")
def health():
    return {"status": "ok"}

@router.post("/predict")
def predict(req: PredictRequest):
    payload = req.model_dump()
    feature_cols = Q["feature_cols"]

    # ✅ now returns (X, fallback_level)
    X, fallback_level = build_features(payload, feature_cols)

    # DEBUG
    nonzero = int((X.iloc[0].to_numpy() != 0).sum())
    nz_cols = X.columns[(X.iloc[0] != 0)].tolist()[:12]
    print("\n================ PREDICT DEBUG ================")
    print("Incoming payload:", payload)
    print("Fallback level:", fallback_level)
    print("Non-zero feature count:", nonzero)
    print("Sample non-zero features:", {c: float(X.iloc[0][c]) for c in nz_cols})
    print("================================================\n")

    q10 = float(Q["q10"].predict(X)[0])
    q50 = float(Q["q50"].predict(X)[0])
    q90 = float(Q["q90"].predict(X)[0])

    return {
        "commodity": req.commodity,
        "state": req.state,
        "market": req.market,
        "arrival_date": req.arrival_date,
        "q10": q10,
        "q50": q50,
        "q90": q90,
        "interval_width": float(q90 - q10),
        # ✅ expose fallback so UI can show a badge
        "fallback_level": fallback_level,
    }