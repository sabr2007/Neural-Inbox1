"""
FastAPI application for Neural Inbox Mini App API.
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routes import items, tasks, projects, search

# Create FastAPI app
app = FastAPI(
    title="Neural Inbox API",
    description="API for Neural Inbox Telegram Mini App",
    version="1.0.0"
)

# CORS middleware - allow all origins for Mini App
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include routers
app.include_router(items.router)
app.include_router(tasks.router)
app.include_router(projects.router)
app.include_router(search.router)


@app.get("/api/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "ok"}
