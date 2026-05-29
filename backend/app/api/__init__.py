from fastapi import APIRouter
from app.api.endpoints import screener, market, llm

api_router = APIRouter()

api_router.include_router(screener.router, prefix="/screener", tags=["Screener"])
api_router.include_router(market.router, prefix="/market", tags=["Market Data"])
api_router.include_router(llm.router, prefix="/llm", tags=["LLM"])
