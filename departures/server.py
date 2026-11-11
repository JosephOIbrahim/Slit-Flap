"""DEPARTURES — FastAPI server. Serves API + built frontend."""

import asyncio
import logging
import math
import re
from contextlib import asynccontextmanager
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse

from . import db
from . import __version__

# ── Paths ─────────────────────────────────────────────────────────

DIST_DIR = Path(__file__).parent / "frontend" / "dist"

# ── Session tracking ──────────────────────────────────────────────

_session_started_at: str = ""

# ── Daily backup ──────────────────────────────────────────────────

log = logging.getLogger("uvicorn.error")
_backup_day: date | None = None


def _today() -> date:
    return date.today()


async def _daily_backup() -> None:
    """Snapshot the board on the first start or request of each local day
    (the server can stay up for days, so startup alone isn't enough)."""
    global _backup_day
    today = _today()
    if _backup_day == today or not db.DB_PATH.exists():
        return
    _backup_day = today  # claim the day first, so concurrent requests skip
    try:
        await asyncio.to_thread(db.backup_daily, today)
    except Exception as exc:  # a failed backup must never take the board down
        log.warning("DEPARTURES daily backup failed: %s", exc)


# ── Lifespan ──────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    global _session_started_at
    await _daily_backup()  # before init, so it captures exactly what's on disk
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


# ── Backup middleware (runs after auth: only admitted requests) ───

@app.middleware("http")
async def daily_backup_middleware(request: Request, call_next):
    await _daily_backup()
    return await call_next(request)


# ── Auth middleware ───────────────────────────────────────────────

# An invite link is exactly /join/<token>; tokens are URL-safe base64.
_JOIN_PATH = re.compile(r"/join/[A-Za-z0-9_-]+")


@app.middleware("http")
async def auth_middleware(request: Request, call_next):
    # The decoded path, exactly as the router will see it.
    path = request.scope["path"]

    # Invite links must work before the visitor has a cookie. Nothing else
    # skips the checks below — the owner is local and viewers carry a cookie.
    if _JOIN_PATH.fullmatch(path):
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


def require_owner(request: Request) -> None:
    """Route guard: only the board's owner (this machine) gets through."""
    if getattr(request.state, "role", None) != "owner":
        raise HTTPException(status_code=403, detail="Owner only")


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
    role = getattr(request.state, "role", "viewer")
    email = getattr(request.state, "viewer_email", None)
    return {"role": role, "email": email}


# Viewer links are keys to the board: only the owner may see or change them.

@app.get("/api/viewers", dependencies=[Depends(require_owner)])
async def list_viewers():
    return await db.list_viewers()


@app.post("/api/viewers", dependencies=[Depends(require_owner)])
async def add_viewer(request: Request):
    body = await request.json()
    email = body.get("email", "").strip()
    if not email or "@" not in email:
        return JSONResponse({"error": "Valid email required"}, status_code=400)
    return await db.add_viewer(email)


@app.delete("/api/viewers/{vid}", dependencies=[Depends(require_owner)])
async def remove_viewer(vid: str):
    return await db.remove_viewer(vid)


# ── Static file serving ──────────────────────────────────────────
#
# Only plain file names inside the built frontend are ever served, e.g.
# "index.html" or "assets/index-Db_14rvD.js". Every path segment is
# checked as text *before* anything touches the disk: on Windows, merely
# asking whether a path exists can reach outside the folder (a drive
# letter, a network share, a device name).

_SAFE_SEGMENT = re.compile(r"[A-Za-z0-9_-][A-Za-z0-9._-]*")
_WINDOWS_DEVICES = {"CON", "PRN", "AUX", "NUL"} | {
    f"{kind}{n}" for kind in ("COM", "LPT") for n in range(10)
}
_NOT_BUILT = {"error": "Frontend not built. Run: cd frontend && npm run build"}


def _is_safe_segment(segment: str) -> bool:
    return (
        _SAFE_SEGMENT.fullmatch(segment) is not None
        and not segment.endswith(".")
        and segment.split(".")[0].upper() not in _WINDOWS_DEVICES
    )


def _dist_file(rel_path: str) -> Path | None:
    """The real file inside DIST_DIR that rel_path names, or None."""
    parts = rel_path.split("/")
    if not all(_is_safe_segment(p) for p in parts):
        return None
    root = DIST_DIR.resolve()
    try:
        found = root.joinpath(*parts).resolve(strict=True)
    except (OSError, RuntimeError):
        return None
    if found.is_relative_to(root) and found.is_file():
        return found
    return None


def _index() -> FileResponse | JSONResponse:
    index = _dist_file("index.html")
    if index is None:
        return JSONResponse(_NOT_BUILT, status_code=404)
    # Always revalidate: a cached page can point at assets a rebuild removed.
    return FileResponse(index, headers={"Cache-Control": "no-cache"})


@app.get("/")
async def serve_root():
    return _index()


# Built files by name; any other non-API path gets the board itself.
@app.get("/{full_path:path}")
async def serve_static(full_path: str):
    if full_path == "api" or full_path.startswith("api/"):
        return JSONResponse({"error": "Not found"}, status_code=404)
    found = _dist_file(full_path)
    if found is None or found.name == "index.html":
        return _index()
    return FileResponse(found)
