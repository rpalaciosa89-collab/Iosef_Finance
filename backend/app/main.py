# DEPRECATED — 2026-06-10 (Ola 4)
# Este archivo ya NO es el entrypoint canónico.
# El backend se ejecuta con: uvicorn server:app
# Las rutas antes exclusivas de main.py han sido migradas a server.py.
#
# Para desarrollo, usar:
#   cd backend && JWT_SECRET_KEY=dev-secret uvicorn server:app --reload --port 8002

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.api import api_router

import warnings
warnings.warn("app.main:app is deprecated. Use server:app instead.", DeprecationWarning, stacklevel=2)

app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    openapi_url=f"{settings.API_V1_STR}/openapi.json",
)

if settings.BACKEND_CORS_ORIGINS:
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[str(origin).strip("/") for origin in settings.BACKEND_CORS_ORIGINS],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

app.include_router(api_router, prefix=settings.API_V1_STR)


@app.get("/", tags=["General"])
def health_check():
    return {
        "status": "healthy",
        "project": settings.PROJECT_NAME,
        "version": settings.VERSION,
        "api_docs_url": "/docs"
    }
