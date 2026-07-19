"""
FastAPI application for the Jit system.

Provides RESTful API endpoints for tax calculation, legal analysis,
compliance checking, risk assessment, and optimization.
"""

from __future__ import annotations

from pathlib import Path

import uvicorn
from fastapi import FastAPI, Response
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from jit.api.middleware import RequestLoggingMiddleware
from jit.api.routers import accounting, legal, algorithms, health, platform

STATIC_DIR = Path(__file__).parent / "static"

app = FastAPI(
    title="Jit - Automatic Recursive Algorithmic Accounting & Legal Analysis System",
    description=(
        "Comprehensive accounting and legal analysis for American citizens. "
        "Provides tax calculation, deduction optimization, legal document analysis, "
        "compliance checking, and recursive algorithmic recommendations."
    ),
    version="0.1.0",
    contact={
        "name": "Jit Project",
        "url": "https://github.com/thetruezubzero-pixel/Jit-",
    },
    license_info={"name": "MIT"},
)

# CORS middleware — configure origins appropriately for production
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Request logging / timing middleware — runs between the frontend, the
# reverse-proxy layer, and the routers below.
app.add_middleware(RequestLoggingMiddleware)

# Include routers
app.include_router(health.router, prefix="/health", tags=["Health"])
app.include_router(accounting.router, prefix="/api/v1/accounting", tags=["Accounting"])
app.include_router(legal.router, prefix="/api/v1/legal", tags=["Legal"])
app.include_router(algorithms.router, prefix="/api/v1/algorithms", tags=["Algorithms"])
app.include_router(platform.router, prefix="/api/v1/platform", tags=["Platform"])

# Bundled single-page frontend, served directly by this API.
app.mount("/ui", StaticFiles(directory=STATIC_DIR, html=True), name="ui")


@app.get("/", include_in_schema=False)
async def root() -> RedirectResponse:
    """Redirect the root path to the bundled frontend."""
    return RedirectResponse(url="/ui/")


@app.get("/favicon.ico", include_in_schema=False)
async def favicon() -> Response:
    return Response(status_code=204)


def run() -> None:
    """Run the Jit API server using Uvicorn."""
    uvicorn.run("jit.api.main:app", host="0.0.0.0", port=8000, reload=True)


if __name__ == "__main__":
    run()
