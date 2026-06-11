"""DEPARTURES — FastAPI server. Serves API + built frontend."""

import math
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

from . import db
from . import __version__

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

app = FastAPI(title="DEPARTURES", version=__version__, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origin_regex=r"http://localhost(:\d+)?",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Auth middleware ───────────────────────────────────────────────

@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    path = request.url.path

    # Always allow: join page, static assets, API docs
    if path.startswith("/join/") or path.startswith("/assets/") or path in ("/favicon.ico",):
        return await call_next(request)

    # Owner: localhost always has full access
    client_host = request.client.host if request.client else ""
    if client_host in ("127.0.0.1", "::1"):
        request.state.role = "owner"
        return await call_next(request)

    # Check viewer token (cookie or query param)
    token = request.cookies.get("viewer_token") or request.query_params.get("token")
    if token:
        viewer = await db.get_viewer_by_token(token)
        if viewer:
            request.state.role = "viewer"
            request.state.viewer_email = viewer["email"]
            # Touch last_seen
            await db.touch_viewer(viewer["id"])

            # Viewers can only GET (read-only)
            if request.method not in ("GET", "HEAD", "OPTIONS"):
                return JSONResponse({"error": "Viewers have read-only access"}, status_code=403)

            response = await call_next(request)
            # Set cookie if it came from query param
            if not request.cookies.get("viewer_token"):
                response.set_cookie("viewer_token", token, httponly=True, max_age=30*86400, samesite="lax")
            return response

    # No auth from remote host → 401
    if path.startswith("/api/"):
        return JSONResponse({"error": "Unauthorized. Use an invite link to access."}, status_code=401)

    # For non-API paths from remote without auth
    return JSONResponse({"error": "Unauthorized. You need an invite link to view this board."}, status_code=401)


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


# ── Auth + Viewer endpoints ──────────────────────────────────────

@app.get("/join/{token}")
async def join_board(token: str):
    viewer = await db.get_viewer_by_token(token)
    if not viewer:
        return JSONResponse({"error": "Invalid or expired invite link"}, status_code=404)
    # Set cookie and redirect to board
    response = RedirectResponse(url="/", status_code=302)
    response.set_cookie("viewer_token", token, httponly=True, max_age=30*86400, samesite="lax")
    return response


@app.get("/api/me")
async def get_me(request: Request):
    role = getattr(request.state, "role", "owner")
    email = getattr(request.state, "viewer_email", None)
    return {"role": role, "email": email}


@app.get("/api/viewers")
async def list_viewers():
    return await db.list_viewers()


@app.post("/api/viewers")
async def add_viewer(request: Request):
    body = await request.json()
    email = body.get("email", "").strip()
    if not email or "@" not in email:
        return JSONResponse({"error": "Valid email required"}, status_code=400)
    return await db.add_viewer(email)


@app.delete("/api/viewers/{vid}")
async def remove_viewer(vid: str):
    return await db.remove_viewer(vid)


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
