from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

# ✅ Import routers (adjust paths if your filenames differ)
from backend.app.api.routes_predict import router as predict_router
from backend.app.api.meta import router as meta_router


def create_app() -> FastAPI:
    app = FastAPI(
        title="Agri Price Forecast API",
        version="1.0.0",
    )

    # ✅ CORS for React frontend
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[
            "http://localhost:5173",
            "http://127.0.0.1:5173",
        ],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ✅ Health
    @app.get("/health")
    def health():
        return {"status": "ok"}

    # ✅ Routers
    app.include_router(predict_router, tags=["predict"])
    app.include_router(meta_router, tags=["meta"])

    return app


app = create_app()