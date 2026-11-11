"""DEPARTURES — FastAPI server. Serves API + built frontend."""

import asyncio
import logging
import math
import os
import re
import time
from contextlib import asynccontextmanager
from dataclasses import dataclass
from datetime import date, datetime, timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from typing import Any

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse, Response

from . import db
from . import __version__

# ── Paths ─────────────────────────────────────────────────────────

DIST_DIR = Path(__file__).parent / "frontend" / "dist"

# ── Session tracking ──────────────────────────────────────────────

_session_started_at: str = ""

# ── Daily backup ──────────────────────────────────────────────────

log = logging.getLogger("uvicorn.error")
BACKUP_RETRY_SECONDS = 30 * 60  # after a failed daily backup, try again this much later


@dataclass
class _Backups:
    """Where the daily backup stands in this server process."""
    day: date | None = None  # the day whose backup is done
    running: bool = False    # one is in progress; other requests don't wait for it
    retry_at: float = 0.0    # after a failure, not tried again before this (_clock time)
    failed: bool = False     # the latest attempt failed (the board's header shows it)
    problem: str | None = None  # "damaged" if the copy failed its check, else "failed"


_backups = _Backups()


def _today() -> date:
    return date.today()


def _clock() -> float:
    return time.monotonic()


async def _daily_backup() -> None:
    """Snapshot the board on the first start or request of each local day
    (the server can stay up for days, so startup alone isn't enough). A
    backup that fails is tried again BACKUP_RETRY_SECONDS later."""
    state, today = _backups, _today()
    if state.day == today or state.running or _clock() < state.retry_at:
        return
    if not db.DB_PATH.exists():
        return
    state.running = True
    try:
        await asyncio.to_thread(db.backup_daily, today)
    except Exception as exc:  # a failed backup must never take the board down
        state.retry_at = _clock() + BACKUP_RETRY_SECONDS
        state.failed = True
        state.problem = "damaged" if isinstance(exc, db.BackupCheckFailed) else "failed"
        if isinstance(exc, db.BackupCheckFailed):
            last = db.last_daily_backup()
            log.error("DEPARTURES daily backup failed, and the board itself may be damaged: %s. "
                      "Newest good backup: %s. See them all with: departures restore",
                      exc, last.name if last else "none yet")
        else:
            log.warning("DEPARTURES daily backup failed (trying again in %d minutes): %s",
                        BACKUP_RETRY_SECONDS // 60, exc)
    else:
        state.day = today
        state.failed = False
        state.problem = None
    finally:
        state.running = False


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

# No CORS: the board's own page calls /api on the same origin, and the Vite
# dev server proxies /api (frontend/vite.config.js). Allowing other origins
# let any page served from another localhost port read and change the board.


# ── Backup middleware (runs after auth: only admitted requests) ───

@app.middleware("http")
async def daily_backup_middleware(request: Request, call_next):
    # Auth names every admitted caller (owner or invited viewer). Invite links
    # pass auth before anyone is known, so a made-up /join/... from the
    # network must not be able to choose when the day's backup is taken.
    if getattr(request.state, "role", None):
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
    updated = await db.update_project(pid, body)
    if updated is None:
        return JSONResponse({"error": "No such project"}, status_code=404)
    return updated


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
async def session(request: Request):
    info: dict[str, Any] = {
        "startedAt": _session_started_at,
        "elapsedMinutes": _elapsed_minutes(),
    }
    # Backup health is the owner's business only (and never the raw error,
    # which names folders on this PC): the header warns when it's failing.
    if getattr(request.state, "role", None) == "owner":
        last = db.last_daily_backup()
        info["backupFailed"] = _backups.failed
        info["backupProblem"] = _backups.problem
        info["lastBackup"] = last.stem.removeprefix("departures-") if last else None
    return info


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
# The server lists the built frontend's files itself and serves a request
# only when it names one of them exactly ("index.html",
# "assets/index-Db_14rvD.js"). A path from a request is never handed to the
# filesystem, so drive letters, network shares, device names, "..", links
# and odd encodings have nothing to work with, while a file with "@",
# spaces or brackets in its name is still served.

_NOT_BUILT = {"error": "Frontend not built. Run: cd frontend && npm run build"}
_NOT_FOUND = {"error": "Not found"}


def _dist_files() -> dict[str, Path]:
    """Every real file inside DIST_DIR, keyed by its URL path."""
    root = DIST_DIR.resolve()
    found: dict[str, Path] = {}
    if not root.is_dir():
        return found
    for folder, subfolders, names in os.walk(root):
        subfolders[:] = [s for s in subfolders if not s.startswith(".")]
        for name in names:
            if name.startswith("."):
                continue
            path = Path(folder) / name
            try:
                real = path.resolve(strict=True)
            except (OSError, RuntimeError):
                continue
            if real.is_relative_to(root) and real.is_file():  # links stay inside
                found[path.relative_to(root).as_posix()] = real
    return found


def _not_modified(request: Request, response: Response) -> bool:
    """True when the browser's cached copy is still current (send a 304)."""
    etag = response.headers.get("etag")
    if_none_match = request.headers.get("if-none-match")
    if if_none_match is not None:
        tags = {t.strip() for t in if_none_match.split(",")}
        return etag is not None and ("*" in tags or etag in tags or f"W/{etag}" in tags)
    since, modified = request.headers.get("if-modified-since"), response.headers.get("last-modified")
    if since and modified:
        try:
            return parsedate_to_datetime(since) >= parsedate_to_datetime(modified)
        except (TypeError, ValueError):
            return False
    return False


def _send_file(path: Path, request: Request, cache_control: str) -> Response:
    response = FileResponse(path, stat_result=os.stat(path), headers={"Cache-Control": cache_control})
    if _not_modified(request, response):
        keep = ("etag", "last-modified", "cache-control")
        return Response(status_code=304, headers={k: response.headers[k] for k in keep if k in response.headers})
    return response


def _index(request: Request, files: dict[str, Path] | None = None) -> Response:
    index = (files if files is not None else _dist_files()).get("index.html")
    if index is None:
        return JSONResponse(_NOT_BUILT, status_code=404)
    # Always revalidate: a cached page can point at assets a rebuild removed.
    return _send_file(index, request, "no-cache")


@app.api_route("/", methods=["GET", "HEAD"])
async def serve_root(request: Request):
    return _index(request)


# Built files by exact name. A request that names a file that isn't there
# gets a 404; any other path (no file name) gets the board itself.
@app.api_route("/{full_path:path}", methods=["GET", "HEAD"])
async def serve_static(full_path: str, request: Request):
    if full_path == "api" or full_path.startswith("api/"):
        return JSONResponse(_NOT_FOUND, status_code=404)
    files = _dist_files()
    found = files.get(full_path)
    if found is None:
        if "." in full_path.rsplit("/", 1)[-1]:
            return JSONResponse(_NOT_FOUND, status_code=404)
        return _index(request, files)
    if full_path == "index.html":
        return _index(request, files)
    # Vite names everything under assets/ by its content hash, so a given
    # name never changes: browsers may keep it for a year without asking.
    if full_path.startswith("assets/"):
        return _send_file(found, request, "public, max-age=31536000, immutable")
    return _send_file(found, request, "no-cache")
