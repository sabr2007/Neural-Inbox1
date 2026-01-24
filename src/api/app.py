"""
FastAPI application for Neural Inbox Mini App API.
"""
import os

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.api.routes import items, tasks, projects, search, user

# Allowed origins for Telegram Mini App
# Telegram WebApp domains + custom webapp URL if configured
TELEGRAM_WEBAPP_ORIGINS = [
    "https://web.telegram.org",
    "https://webk.telegram.org",
    "https://webz.telegram.org",
]

def _get_allowed_origins() -> list[str]:
    """Build list of allowed CORS origins."""
    origins = TELEGRAM_WEBAPP_ORIGINS.copy()

    # Add custom webapp URL if configured
    webapp_url = os.getenv("WEBAPP_URL")
    if webapp_url:
        # Extract origin from URL (scheme + host)
        from urllib.parse import urlparse
        parsed = urlparse(webapp_url)
        origin = f"{parsed.scheme}://{parsed.netloc}"
        if origin not in origins:
            origins.append(origin)

    # Allow localhost for development only if DEBUG is enabled
    if os.getenv("DEBUG", "false").lower() == "true":
        origins.extend([
            "http://localhost:5173",
            "http://localhost:3000",
            "http://127.0.0.1:5173",
            "http://127.0.0.1:3000",
        ])

    return origins

ALLOWED_ORIGINS = _get_allowed_origins()

# Create FastAPI app
app = FastAPI(
    title="Neural Inbox API",
    description="API for Neural Inbox Telegram Mini App",
    version="1.0.0"
)

# CORS middleware - strict allowlist for Telegram WebApp domains
app.add_middleware(
    CORSMiddleware,
    allow_origins=ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "DELETE", "PATCH"],
    allow_headers=["Authorization", "Content-Type", "X-Telegram-Init-Data"],
)

# Include routers
app.include_router(items.router)
app.include_router(tasks.router)
app.include_router(projects.router)
app.include_router(search.router)
app.include_router(user.router)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
