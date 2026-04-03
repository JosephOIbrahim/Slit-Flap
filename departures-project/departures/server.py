"""DEPARTURES — FastAPI server. Serves API + built frontend."""

import math
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import db

# ── Paths ─────────────────────────────────────────────────────────

DIST_DIR = Path(__file__).parent / "frontend" / "dist"

# ── Session tracking ──────────────────────────────────────────────

_session_started_at: str = ""


# ── Lifespan ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _session_started_at
    await db.init_db()
    _session_started_at = datetime.now(timezone.utc).isoformat()
    yield


# ── App ───────────────────────────────────────────────────────────

app = FastAPI(title="DEPARTURES", version="0.4.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helper ────────────────────────────────────────────────────────

def _elapsed_minutes() -> int:
    if not _session_started_at:
        return 0
    started = datetime.fromisoformat(_session_started_at)
    now = datetime.now(timezone.utc)
    return math.floor((now - started).total_seconds() / 60)


# ── Project endpoints ─────────────────────────────────────────────

@app.get("/api/projects")
async def list_projects():
    return await db.list_projects()


@app.post("/api/projects")
async def create_project(request: Request):
    body = await request.json()
    return await db.create_project(body)


@app.put("/api/projects/{pid}")
async def update_project(pid: str, request: Request):
    body = await request.json()
    return await db.update_project(pid, body)


@app.delete("/api/projects/{pid}")
async def delete_project(pid: str):
    return await db.delete_project(pid)


# ── Log endpoints ─────────────────────────────────────────────────

@app.get("/api/projects/{pid}/logs")
async def get_logs(pid: str):
    return await db.get_logs(pid)


@app.post("/api/projects/{pid}/logs")
async def add_log(pid: str, request: Request):
    body = await request.json()
    text = body.get("text", "")
    return await db.add_log(pid, text)


# ── Notes endpoints ───────────────────────────────────────────────

@app.get("/api/projects/{pid}/notes")
async def get_notes(pid: str):
    return await db.get_notes(pid)


@app.put("/api/projects/{pid}/notes")
async def update_notes(pid: str, request: Request):
    body = await request.json()
    content = body.get("content", "")
    return await db.update_notes(pid, content)


# ── Recap + Session ───────────────────────────────────────────────

@app.get("/api/recap")
async def recap():
    data = await db.get_recap()
    data["sessionMinutes"] = _elapsed_minutes()
    return data


@app.get("/api/session")
async def session():
    return {
        "startedAt": _session_started_at,
        "elapsedMinutes": _elapsed_minutes(),
    }


# ── Seed endpoint (for dev convenience) ──────────────────────────

@app.post("/api/seed")
async def seed():
    await db.seed_db()
    return {"seeded": True}


# ── Event endpoints ──────────────────────────────────────────────

@app.get("/api/events")
async def list_events():
    return await db.list_events()


@app.post("/api/events")
async def create_event(request: Request):
    body = await request.json()
    return await db.create_event(body)


@app.put("/api/events/{eid}")
async def update_event(eid: str, request: Request):
    body = await request.json()
    return await db.update_event(eid, body)


@app.delete("/api/events/{eid}")
async def delete_event(eid: str):
    return await db.delete_event(eid)


# ── Settings endpoints ───────────────────────────────────────────

@app.get("/api/settings")
async def get_settings():
    return await db.get_settings()


@app.put("/api/settings")
async def update_settings(request: Request):
    body = await request.json()
    return await db.update_settings(body)


# ── Static file serving ──────────────────────────────────────────

# Mount static assets from the built frontend (JS, CSS, images, fonts)
if DIST_DIR.exists():
    app.mount("/assets", StaticFiles(directory=str(DIST_DIR / "assets")), name="assets")


# Serve index.html for the root
@app.get("/")
async def serve_root():
    index = DIST_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return JSONResponse(
        {"error": "Frontend not built. Run: cd frontend && npm run build"},
        status_code=404,
    )


# SPA catch-all: all non-API routes fall back to index.html
@app.get("/{full_path:path}")
async def spa_fallback(full_path: str):
    # First check if it's a real static file in dist
    candidate = DIST_DIR / full_path
    if candidate.exists() and candidate.is_file():
        return FileResponse(str(candidate))
    # Otherwise serve index.html for SPA routing
    index = DIST_DIR / "index.html"
    if index.exists():
        return FileResponse(str(index))
    return JSONResponse(
        {"error": "Frontend not built. Run: cd frontend && npm run build"},
        status_code=404,
    )
