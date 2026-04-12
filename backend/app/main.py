from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from app.config import settings
from app.middleware.request_id import RequestIdMiddleware
from app.middleware.logging import LoggingMiddleware
from app.middleware.rate_limit import RateLimitMiddleware
from app.middleware.auth import AuthMiddleware

app = FastAPI(title="FORGE", version="0.1.0")

# ── Middleware (order matters: first added = outermost) ──────────
# 5. Auth (innermost — runs last on request, first on response)
app.add_middleware(AuthMiddleware)
# 4. Rate limit
app.add_middleware(RateLimitMiddleware)
# 3. CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
# 2. Logging
app.add_middleware(LoggingMiddleware)
# 1. Request ID (outermost — runs first on request)
app.add_middleware(RequestIdMiddleware)


# ── Health ───────────────────────────────────────────────────────
@app.get("/health")
async def health() -> dict:
    return {"status": "ok", "env": settings.FORGE_ENV}


# ── API routers ──────────────────────────────────────────────────
from app.api.v1.auth import router as auth_router
from app.api.v1.projects import router as projects_router
from app.api.v1.pipeline import router as pipeline_router

app.include_router(auth_router)
app.include_router(projects_router)
app.include_router(pipeline_router)


# ── Inngest endpoint ─────────────────────────────────────────────
# inngest.fast_api.serve() mounts POST /api/inngest directly on the app
from inngest.fast_api import serve as inngest_serve
from app.inngest_client import forge_inngest

inngest_serve(app, forge_inngest, functions=[], serve_path="/api/inngest")
