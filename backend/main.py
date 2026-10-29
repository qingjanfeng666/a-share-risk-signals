"""FastAPI entry point for the local project demo."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.auth import router as auth_router
from backend.api.routes import router
from backend.config import FRONTEND_ORIGINS


app = FastAPI(title="A 股风险信号 API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=FRONTEND_ORIGINS,
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
    allow_credentials=True,
)


@app.middleware("http")
async def private_api_cache_control(request, call_next):
    response = await call_next(request)
    if request.url.path.startswith("/api/") and request.url.path != "/api/health":
        response.headers["Cache-Control"] = "no-store"
    return response

app.include_router(auth_router)
app.include_router(router)
