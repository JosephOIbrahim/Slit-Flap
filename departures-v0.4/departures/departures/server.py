"""
DEPARTURES — Server
FastAPI serving static React frontend + REST API over SQLite.
"""

from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
import json

from . import db

# ─── Session tracking ─────────────────────────────────────────

_session_start = None


def get_session_info():
    global _session_start
    if _session_start is None:
        _session_start = datetime.now(timezone.utc)
    elapsed = (datetime.now(timezone.utc) - _session_start).total_seconds()
    return {
        "startedAt": _session_start.isoformat(),
        "elapsedMinutes": int(elapsed // 60),
        "elapsedSeconds": int(elapsed),
    }


# ─── App ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    await db.init_db()
    global _session_start
    _session_start = datetime.now(timezone.utc)
    yield


app = FastAPI(title="DEPARTURES", version="0.4.0", lifespan=lifespan)

FRONTEND_DIR = Path(__file__).parent / "frontend" / "dist"


# ─── API Routes ───────────────────────────────────────────────

@app.get("/api/projects")
async def list_projects():
    return await db.list_projects()


@app.post("/api/projects")
async def create_project(data: dict):
    return await db.create_project(data)


@app.put("/api/projects/{pid}")
async def update_project(pid: str, data: dict):
    return await db.update_project(pid, data)


@app.delete("/api/projects/{pid}")
async def delete_project(pid: str):
    return await db.delete_project(pid)


@app.post("/api/projects/{pid}/log")
async def add_log(pid: str, data: dict):
    text = data.get("text", "")
    if not text.strip():
        raise HTTPException(400, "Log text required")
    return await db.add_log(pid, text)


@app.get("/api/recap")
async def recap():
    recap_data = await db.get_recap()
    session = get_session_info()
    recap_data["sessionMinutes"] = session["elapsedMinutes"]
    return recap_data


@app.get("/api/session")
async def session():
    return get_session_info()


# ─── Frontend ─────────────────────────────────────────────────

@app.get("/")
async def root():
    index = FRONTEND_DIR / "index.html"
    if index.exists():
        return FileResponse(index)
    return {"error": "Frontend not built. Run the build step first.", "hint": "See README.md"}


# Mount static files (JS, CSS, assets) if dist directory exists
if FRONTEND_DIR.exists():
    app.mount("/static", StaticFiles(directory=FRONTEND_DIR), name="static")
