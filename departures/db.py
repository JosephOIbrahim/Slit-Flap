"""DEPARTURES — SQLite data layer (aiosqlite)."""

import json
import os
import secrets
import uuid
from datetime import datetime, timezone, date
from pathlib import Path

import aiosqlite

DB_DIR = Path.home() / ".departures"
DB_PATH = DB_DIR / "departures.db"

# ── Column ↔ camelCase maps ──────────────────────────────────────

_COL_TO_CAMEL = {
    "next_action": "next",
    "bg_color": "bgColor",
    "mile_total": "of",
    "today_time": "todayTime",
    "sort_order": "sortOrder",
    "last_touched": "lastTouched",
    "created_at": "createdAt",
    "updated_at": "updatedAt",
}

_CAMEL_TO_COL = {v: k for k, v in _COL_TO_CAMEL.items()}

_PROJECT_COLS = [
    "id", "name", "status", "track", "domain", "next_action",
    "deadline", "bg_color", "mile", "mile_total", "today_time",
    "sort_order", "last_touched", "created_at", "updated_at",
]


def _to_camel(col: str) -> str:
    return _COL_TO_CAMEL.get(col, col)


def _to_col(key: str) -> str:
    return _CAMEL_TO_COL.get(key, key)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


async def _conn() -> aiosqlite.Connection:
    DB_DIR.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(DB_PATH))
    await db.execute("PRAGMA journal_mode=WAL")
    await db.execute("PRAGMA foreign_keys=ON")
    db.row_factory = aiosqlite.Row
    return db


# ── Schema ────────────────────────────────────────────────────────

_SCHEMA = """
CREATE TABLE IF NOT EXISTS projects (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    status TEXT DEFAULT 'QUEUED',
    track TEXT DEFAULT '03',
    domain TEXT DEFAULT 'AI',
    next_action TEXT DEFAULT '',
    deadline TEXT DEFAULT '',
    bg_color TEXT DEFAULT '',
    mile INTEGER DEFAULT 0,
    mile_total INTEGER DEFAULT 0,
    today_time TEXT DEFAULT '',
    sort_order INTEGER DEFAULT 0,
    last_touched TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS notes (
    project_id TEXT PRIMARY KEY,
    content TEXT DEFAULT '',
    updated_at TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    projects_touched TEXT DEFAULT '[]',
    summary TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS events (
    id TEXT PRIMARY KEY,
    time TEXT NOT NULL,
    end_time TEXT DEFAULT '',
    name TEXT NOT NULL,
    source TEXT DEFAULT '',
    linked_project TEXT DEFAULT '',
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS settings (
    key TEXT PRIMARY KEY,
    value TEXT DEFAULT ''
);

CREATE TABLE IF NOT EXISTS viewers (
    id TEXT PRIMARY KEY,
    email TEXT NOT NULL,
    token TEXT UNIQUE NOT NULL,
    created_at TEXT,
    last_seen TEXT
);
"""

# ── Seed data ─────────────────────────────────────────────────────

SEEDS = [
    ("brand-refresh", "Brand Refresh", "ACTIVE", "01", "MIX", "Finalize color palette + type system", 3, 6, "10:00"),
    ("product-launch", "Product Launch", "ACTIVE", "01", "OPS", "Review launch timeline with team", 1, 4, "14:00"),
    ("motion-system", "Motion System", "BLOCKED", "01", "VFX", "Waiting on asset delivery", 2, 5, ""),
    ("icon-library", "Icon Library", "SHIPPED", "02", "MIX", "Final QA pass complete", 8, 8, ""),
    ("ar-prototype", "AR Prototype", "ACTIVE", "02", "AI", "Integrate gesture recognition", 1, 4, "16:00"),
    ("design-system", "Design System", "ROLLING", "02", "WEB", "Component audit + documentation", 5, 8, ""),
    ("render-pipeline", "Render Pipeline", "QUEUED", "02", "VFX", "Evaluate new GPU shaders", 0, 5, ""),
    ("type-specimen", "Type Specimen", "QUEUED", "03", "MIX", "Specimen book layout + print", 0, 5, ""),
    ("3d-scanning", "3D Scanning", "ACTIVE", "03", "VFX", "Calibrate photogrammetry rig", 1, 3, ""),
    ("voice-agent", "Voice Agent", "QUEUED", "03", "AI", "NLU training data collection", 0, 4, ""),
    ("showreel", "Showreel", "QUEUED", "03", "VFX", "Cut new 2-minute reel", 0, 3, ""),
    ("portfolio-site", "Portfolio Site", "QUEUED", "03", "WEB", "Redesign with new work", 0, 4, ""),
    ("studio-blog", "Studio Blog", "QUEUED", "03", "WEB", "Monthly case study post", 0, 2, ""),
    ("client-portal", "Client Portal", "BLOCKED", "04", "WEB", "API integration pending", 0, 3, ""),
    ("departures", "This App", "ACTIVE", "03", "WEB", "Iterate design + features", 3, 5, "11:00"),
    ("ml-pipeline", "ML Pipeline", "QUEUED", "04", "AI", "Training infrastructure setup", 0, 4, ""),
]

SEED_EVENTS = [
    ("ev1", "09:00", "09:30", "Morning standup", "Calendar", ""),
    ("ev2", "11:30", "12:00", "Client review call", "Calendar", ""),
    ("ev3", "13:00", "13:30", "Lunch break", "Calendar", ""),
    ("ev4", "15:00", "15:30", "Design critique session", "Calendar", "brand-refresh"),
    ("ev5", "17:30", "18:00", "End of day wrap-up", "Calendar", ""),
]

_SEED_AGES = {
    "brand-refresh": 0.5, "product-launch": 2, "motion-system": 5, "icon-library": 14,
    "ar-prototype": 1, "design-system": 0.2, "render-pipeline": 8, "type-specimen": 12,
    "3d-scanning": 3, "voice-agent": 10, "showreel": 20, "portfolio-site": 7,
    "studio-blog": 15, "client-portal": 18, "departures": 0, "ml-pipeline": 25,
}


async def _insert_seeds(db: aiosqlite.Connection) -> None:
    now = datetime.now(timezone.utc)
    for sid, name, status, track, domain, next_action, mile, mile_total, today_time in SEEDS:
        age_days = _SEED_AGES.get(sid, 5)
        last_touched = datetime.fromtimestamp(
            now.timestamp() - age_days * 86400, tz=timezone.utc
        ).isoformat()
        created_at = "2026-02-21T00:00:00+00:00"
        updated_at = now.isoformat()
        await db.execute(
            """INSERT INTO projects
               (id, name, status, track, domain, next_action, deadline, bg_color,
                mile, mile_total, today_time, last_touched, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, '', '', ?, ?, ?, ?, ?, ?)""",
            (sid, name, status, track, domain, next_action,
             mile, mile_total, today_time, last_touched, created_at, updated_at),
        )
    # Seed events
    now_str = now.isoformat()
    for eid, time, end_time, name, source, linked in SEED_EVENTS:
        await db.execute(
            "INSERT OR IGNORE INTO events (id, time, end_time, name, source, linked_project, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (eid, time, end_time, name, source, linked, now_str, now_str),
        )
    # Seed default settings
    for key, val in [("zip", ""), ("fontSize", "104"), ("alignment", "left")]:
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))
    await db.commit()


# ── Public API ────────────────────────────────────────────────────

async def init_db() -> None:
    """Create tables and seed if empty."""
    db = await _conn()
    try:
        await db.executescript(_SCHEMA)
        # Migration: add sort_order column if missing (existing DBs)
        try:
            await db.execute("ALTER TABLE projects ADD COLUMN sort_order INTEGER DEFAULT 0")
            await db.commit()
            # Initialize sort_order to sequential values based on current order
            cursor = await db.execute("SELECT id FROM projects ORDER BY track, name")
            rows = await cursor.fetchall()
            for i, row in enumerate(rows):
                await db.execute("UPDATE projects SET sort_order = ? WHERE id = ?", (i, row["id"]))
            await db.commit()
        except Exception:
            # Column already exists — ensure sort_orders are unique
            cursor = await db.execute("SELECT COUNT(DISTINCT sort_order) as cnt, COUNT(*) as total FROM projects")
            row = await cursor.fetchone()
            if row["cnt"] < row["total"]:
                # All same value — assign sequential
                cursor2 = await db.execute("SELECT id FROM projects ORDER BY sort_order, track, name")
                rows2 = await cursor2.fetchall()
                for i, r in enumerate(rows2):
                    await db.execute("UPDATE projects SET sort_order = ? WHERE id = ?", (i, r["id"]))
                await db.commit()
        cursor = await db.execute("SELECT COUNT(*) FROM projects")
        row = await cursor.fetchone()
        if row[0] == 0:
            await _insert_seeds(db)
        else:
            # Ensure events and settings are seeded even if projects already exist
            now_str = _now()
            ev_cursor = await db.execute("SELECT COUNT(*) FROM events")
            ev_row = await ev_cursor.fetchone()
            if ev_row[0] == 0:
                for eid, time, end_time, name, source, linked in SEED_EVENTS:
                    await db.execute(
                        "INSERT OR IGNORE INTO events (id, time, end_time, name, source, linked_project, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                        (eid, time, end_time, name, source, linked, now_str, now_str),
                    )
            for key, val in [("zip", ""), ("fontSize", "104"), ("alignment", "left")]:
                await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))
            await db.commit()
    finally:
        await db.close()


async def seed_db() -> None:
    """Drop all data and re-insert 16 seed projects."""
    db = await _conn()
    try:
        await db.executescript(_SCHEMA)
        await db.executescript("""
            DELETE FROM logs;
            DELETE FROM notes;
            DELETE FROM sessions;
            DELETE FROM events;
            DELETE FROM settings;
            DELETE FROM viewers;
            DELETE FROM projects;
        """)
        await _insert_seeds(db)
    finally:
        await db.close()


async def list_projects() -> list[dict]:
    """Return all projects with logs attached, camelCase keys."""
    db = await _conn()
    try:
        cursor = await db.execute(
            "SELECT * FROM projects ORDER BY sort_order, track, name"
        )
        rows = await cursor.fetchall()
        projects = []
        for row in rows:
            p = dict(row)
            # Fetch logs for this project
            log_cursor = await db.execute(
                "SELECT text, created_at FROM logs WHERE project_id = ? ORDER BY created_at ASC",
                (p["id"],),
            )
            log_rows = await log_cursor.fetchall()
            logs = [{"text": lr["text"], "at": lr["created_at"]} for lr in log_rows]

            # Build camelCase output
            out = {}
            for col in _PROJECT_COLS:
                out[_to_camel(col)] = p[col]
            out["log"] = logs
            out["history"] = []
            projects.append(out)
        return projects
    finally:
        await db.close()


async def create_project(data: dict) -> dict:
    """Create a project from camelCase frontend data. Returns {id}."""
    now = _now()
    pid = data.get("id") or (
        hex(int(datetime.now(timezone.utc).timestamp() * 1000))[2:]
        + uuid.uuid4().hex[:6]
    )
    db = await _conn()
    try:
        vals = {
            "id": pid,
            "name": data.get("name", "New Project"),
            "status": data.get("status", "QUEUED"),
            "track": data.get("track", "03"),
            "domain": data.get("domain", "AI"),
            "next_action": data.get("next", ""),
            "deadline": data.get("deadline", ""),
            "bg_color": data.get("bgColor", ""),
            "mile": data.get("mile", 0),
            "mile_total": data.get("of", 0),
            "today_time": data.get("todayTime", ""),
            "last_touched": now,
            "created_at": now,
            "updated_at": now,
        }
        cols = ", ".join(vals.keys())
        placeholders = ", ".join("?" for _ in vals)
        await db.execute(
            f"INSERT INTO projects ({cols}) VALUES ({placeholders})",
            tuple(vals.values()),
        )
        await db.commit()
        return {"id": pid}
    finally:
        await db.close()


async def update_project(pid: str, data: dict) -> dict:
    """Partial update from camelCase dict. Always touches updated_at and last_touched."""
    now = _now()
    db = await _conn()
    try:
        sets = []
        params = []
        for key, value in data.items():
            col = _to_col(key)
            if col in _PROJECT_COLS and col not in ("id", "created_at"):
                sets.append(f"{col} = ?")
                params.append(value)
        # Always update timestamps
        if "updated_at" not in [s.split(" = ")[0] for s in sets]:
            sets.append("updated_at = ?")
            params.append(now)
        if "last_touched" not in [s.split(" = ")[0] for s in sets]:
            sets.append("last_touched = ?")
            params.append(now)

        params.append(pid)
        await db.execute(
            f"UPDATE projects SET {', '.join(sets)} WHERE id = ?",
            params,
        )
        await db.commit()
        return {"id": pid, "updated": True}
    finally:
        await db.close()


async def delete_project(pid: str) -> dict:
    """Delete project and cascade to logs/notes."""
    db = await _conn()
    try:
        # Foreign key cascade handles logs and notes
        await db.execute("DELETE FROM projects WHERE id = ?", (pid,))
        await db.commit()
        return {"id": pid, "deleted": True}
    finally:
        await db.close()


async def add_log(pid: str, text: str) -> dict:
    """Insert a log entry and touch the project. Returns {text, at}."""
    now = _now()
    db = await _conn()
    try:
        await db.execute(
            "INSERT INTO logs (project_id, text, created_at) VALUES (?, ?, ?)",
            (pid, text, now),
        )
        await db.execute(
            "UPDATE projects SET last_touched = ?, updated_at = ? WHERE id = ?",
            (now, now, pid),
        )
        await db.commit()
        return {"text": text, "at": now}
    finally:
        await db.close()


async def get_logs(pid: str) -> list[dict]:
    """Return all logs for a project as [{text, at}]."""
    db = await _conn()
    try:
        cursor = await db.execute(
            "SELECT text, created_at FROM logs WHERE project_id = ? ORDER BY created_at ASC",
            (pid,),
        )
        rows = await cursor.fetchall()
        return [{"text": r["text"], "at": r["created_at"]} for r in rows]
    finally:
        await db.close()


async def get_notes(pid: str) -> dict:
    """Return {content, updatedAt} for a project, or empty defaults."""
    db = await _conn()
    try:
        cursor = await db.execute(
            "SELECT content, updated_at FROM notes WHERE project_id = ?",
            (pid,),
        )
        row = await cursor.fetchone()
        if row:
            return {"content": row["content"], "updatedAt": row["updated_at"]}
        return {"content": "", "updatedAt": None}
    finally:
        await db.close()


async def update_notes(pid: str, content: str) -> dict:
    """Upsert notes for a project. Returns {content, updatedAt}."""
    now = _now()
    db = await _conn()
    try:
        await db.execute(
            """INSERT INTO notes (project_id, content, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(project_id)
               DO UPDATE SET content = excluded.content, updated_at = excluded.updated_at""",
            (pid, content, now),
        )
        await db.commit()
        return {"content": content, "updatedAt": now}
    finally:
        await db.close()


async def get_recap() -> dict:
    """Today's touched projects and log count."""
    today_str = datetime.now(timezone.utc).date().isoformat()
    db = await _conn()
    try:
        # Projects touched today (last_touched starts with today's date)
        cursor = await db.execute(
            "SELECT id, name, status FROM projects WHERE last_touched LIKE ? || '%'",
            (today_str,),
        )
        touched = await cursor.fetchall()
        projects = [{"id": r["id"], "name": r["name"], "status": r["status"]} for r in touched]

        # Log entries created today
        log_cursor = await db.execute(
            "SELECT COUNT(*) FROM logs WHERE created_at LIKE ? || '%'",
            (today_str,),
        )
        log_row = await log_cursor.fetchone()
        log_count = log_row[0]

        return {
            "date": today_str,
            "projectsTouched": len(projects),
            "projects": projects,
            "logEntries": log_count,
        }
    finally:
        await db.close()


# ── Event column ↔ camelCase maps ────────────────────────────────

_EVENT_COL_TO_CAMEL = {
    "end_time": "endTime",
    "linked_project": "linkedProject",
    "created_at": "createdAt",
    "updated_at": "updatedAt",
}

_EVENT_CAMEL_TO_COL = {v: k for k, v in _EVENT_COL_TO_CAMEL.items()}

_EVENT_COLS = [
    "id", "time", "end_time", "name", "source",
    "linked_project", "created_at", "updated_at",
]


def _event_to_camel(col: str) -> str:
    return _EVENT_COL_TO_CAMEL.get(col, col)


def _event_to_col(key: str) -> str:
    return _EVENT_CAMEL_TO_COL.get(key, key)


# ── Event CRUD ───────────────────────────────────────────────────

async def list_events() -> list[dict]:
    """Return all events, camelCase keys."""
    db = await _conn()
    try:
        cursor = await db.execute("SELECT * FROM events ORDER BY time")
        rows = await cursor.fetchall()
        events = []
        for row in rows:
            r = dict(row)
            out = {}
            for col in _EVENT_COLS:
                out[_event_to_camel(col)] = r[col]
            events.append(out)
        return events
    finally:
        await db.close()


async def create_event(data: dict) -> dict:
    """Create event. Returns {id}. Accepts: time, endTime, name, source, linkedProject."""
    now = _now()
    eid = data.get("id") or (
        hex(int(datetime.now(timezone.utc).timestamp() * 1000))[2:]
        + uuid.uuid4().hex[:6]
    )
    db = await _conn()
    try:
        vals = {
            "id": eid,
            "time": data.get("time", ""),
            "end_time": data.get("endTime", ""),
            "name": data.get("name", ""),
            "source": data.get("source", ""),
            "linked_project": data.get("linkedProject", ""),
            "created_at": now,
            "updated_at": now,
        }
        cols = ", ".join(vals.keys())
        placeholders = ", ".join("?" for _ in vals)
        await db.execute(
            f"INSERT INTO events ({cols}) VALUES ({placeholders})",
            tuple(vals.values()),
        )
        await db.commit()
        return {"id": eid}
    finally:
        await db.close()


async def update_event(eid: str, data: dict) -> dict:
    """Partial update. Returns {id, updated: True}. Maps camelCase→snake_case."""
    now = _now()
    db = await _conn()
    try:
        sets = []
        params = []
        for key, value in data.items():
            col = _event_to_col(key)
            if col in _EVENT_COLS and col not in ("id", "created_at"):
                sets.append(f"{col} = ?")
                params.append(value)
        # Always update timestamp
        if "updated_at" not in [s.split(" = ")[0] for s in sets]:
            sets.append("updated_at = ?")
            params.append(now)

        params.append(eid)
        await db.execute(
            f"UPDATE events SET {', '.join(sets)} WHERE id = ?",
            params,
        )
        await db.commit()
        return {"id": eid, "updated": True}
    finally:
        await db.close()


async def delete_event(eid: str) -> dict:
    """Delete event. Returns {id, deleted: True}."""
    db = await _conn()
    try:
        await db.execute("DELETE FROM events WHERE id = ?", (eid,))
        await db.commit()
        return {"id": eid, "deleted": True}
    finally:
        await db.close()


# ── Settings CRUD ────────────────────────────────────────────────

async def get_settings() -> dict:
    """Return all settings as {key: value} dict."""
    db = await _conn()
    try:
        cursor = await db.execute("SELECT key, value FROM settings")
        rows = await cursor.fetchall()
        return {r["key"]: r["value"] for r in rows}
    finally:
        await db.close()


async def update_settings(data: dict) -> dict:
    """Update settings from partial dict. Returns full settings."""
    db = await _conn()
    try:
        for key, value in data.items():
            await db.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value)),
            )
        await db.commit()
        # Return full settings
        cursor = await db.execute("SELECT key, value FROM settings")
        rows = await cursor.fetchall()
        return {r["key"]: r["value"] for r in rows}
    finally:
        await db.close()


# ── Viewer CRUD ──────────────────────────────────────────────────

async def add_viewer(email: str) -> dict:
    """Add a viewer by email. Generates a unique token. Returns {id, email, token, createdAt}."""
    db = await _conn()
    try:
        # Check if email already exists
        cursor = await db.execute(
            "SELECT id, email, token, created_at FROM viewers WHERE email = ?",
            (email,),
        )
        existing = await cursor.fetchone()
        if existing:
            return {
                "id": existing["id"],
                "email": existing["email"],
                "token": existing["token"],
                "createdAt": existing["created_at"],
            }

        now = _now()
        vid = uuid.uuid4().hex[:12]
        token = secrets.token_urlsafe(24)
        await db.execute(
            "INSERT INTO viewers (id, email, token, created_at) VALUES (?, ?, ?, ?)",
            (vid, email, token, now),
        )
        await db.commit()
        return {"id": vid, "email": email, "token": token, "createdAt": now}
    finally:
        await db.close()


async def list_viewers() -> list[dict]:
    """Return all viewers as [{id, email, token, createdAt, lastSeen}]."""
    db = await _conn()
    try:
        cursor = await db.execute(
            "SELECT id, email, token, created_at, last_seen FROM viewers ORDER BY created_at DESC"
        )
        rows = await cursor.fetchall()
        return [
            {
                "id": r["id"],
                "email": r["email"],
                "token": r["token"],
                "createdAt": r["created_at"],
                "lastSeen": r["last_seen"],
            }
            for r in rows
        ]
    finally:
        await db.close()


async def remove_viewer(vid: str) -> dict:
    """Delete a viewer. Returns {id, deleted: True}."""
    db = await _conn()
    try:
        await db.execute("DELETE FROM viewers WHERE id = ?", (vid,))
        await db.commit()
        return {"id": vid, "deleted": True}
    finally:
        await db.close()


async def get_viewer_by_token(token: str) -> dict | None:
    """Look up a viewer by token. Returns {id, email, token} or None."""
    db = await _conn()
    try:
        cursor = await db.execute(
            "SELECT id, email, token FROM viewers WHERE token = ?",
            (token,),
        )
        row = await cursor.fetchone()
        if row:
            return {"id": row["id"], "email": row["email"], "token": row["token"]}
        return None
    finally:
        await db.close()


async def touch_viewer(vid: str) -> None:
    """Update last_seen timestamp for a viewer."""
    now = _now()
    db = await _conn()
    try:
        await db.execute(
            "UPDATE viewers SET last_seen = ? WHERE id = ?",
            (now, vid),
        )
        await db.commit()
    finally:
        await db.close()
