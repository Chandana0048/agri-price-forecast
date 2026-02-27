from fastapi import APIRouter, Query
from backend.app.services import meta_service

router = APIRouter(prefix="/meta", tags=["meta"])

@router.get("/states")
def get_states():
    return {"states": meta_service.states()}

@router.get("/commodities")
def get_commodities():
    return {"commodities": meta_service.commodities()}

@router.get("/markets")
def get_markets(state: str | None = Query(default=None)):
    # If state is provided -> filtered markets, else -> all markets
    return {"markets": meta_service.markets(state)}

@router.get("/districts")
def get_districts(state: str | None = Query(default=None)):
    return {"districts": meta_service.districts(state)}

@router.get("/top-markets")
def get_top_markets(
    state: str | None = Query(default=None),
    commodity: str | None = Query(default=None),
    k: int = Query(default=10, ge=1, le=50),
):
    return {"top_markets": meta_service.top_markets(state=state, commodity=commodity, k=k)}