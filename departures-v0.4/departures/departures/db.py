"""
DEPARTURES — Database Layer
SQLite via aiosqlite. Three tables: projects, logs, sessions.
Stores in ~/.departures/departures.db
"""

import aiosqlite
import json
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path

DB_DIR = Path.home() / ".departures"
DB_PATH = DB_DIR / "departures.db"

SCHEMA = """
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
    last_touched TEXT,
    created_at TEXT,
    updated_at TEXT
);

CREATE TABLE IF NOT EXISTS logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    projects_touched TEXT DEFAULT '[]'
);
"""

# ─── Seeds (Joe's actual project deck) ────────────────────────

SEEDS = [
    ("otto", "Otto OS", "ACTIVE", "01", "AI", "WhatsApp integration + follow-up loop", 1, 6, "10:00"),
    ("patents", "US Patents", "ACTIVE", "01", "OPS", "File USD Cognitive Substrate patent", 0, 3, "14:00"),
    ("use-products", "Use Your Products", "BLOCKED", "01", "OPS", "Synapse + OTTO CLI + Comfy Agent", 0, 4, ""),
    ("comfyui", "ComfyUI Agent", "SHIPPED", "02", "AI", "Refactor + demo", 1, 3, ""),
    ("synapse", "Synapse", "ACTIVE", "02", "MIX", "Refactor for Houdini 21 + demo", 0, 4, "16:00"),
    ("cog-sub", "USD Cog Substrate", "ROLLING", "02", "AI", "General improvements", 5, 8, ""),
    ("carwash", "CarWash Renderer", "QUEUED", "02", "MIX", "Houdini GenAI render pipeline", 0, 5, ""),
    ("translators", "Translators Game", "QUEUED", "03", "MIX", "Game mechanics + intake pipeline", 0, 5, ""),
    ("trellis", "Trellis-2", "ACTIVE", "03", "MIX", "Lightweight USD export", 1, 3, ""),
    ("td-asst", "TD Assistant", "QUEUED", "03", "MIX", "Reimagine Synapse for TouchDesigner", 0, 4, ""),
    ("rtx-remix", "ComfyUI RTX Remix", "QUEUED", "03", "MIX", "", 0, 0, ""),
    ("jaime", "jaimeibrahim.com", "QUEUED", "03", "WEB", "Create MAINTENANCE.md", 0, 2, ""),
    ("joe-site", "josephibrahim.com", "QUEUED", "03", "WEB", "Add Houdini + UE work", 0, 4, ""),
    ("conductor", "aiconductor.studio", "BLOCKED", "04", "WEB", "Rebrand — no longer a conductor", 0, 3, ""),
    ("departures", "Departures App", "ACTIVE", "03", "WEB", "Iterate design + PWA", 1, 5, "11:00"),
    ("isaac", "Isaac Sim LLM", "QUEUED", "04", "AI", "USD Cog Substrate on robotics", 0, 0, ""),
]


def _now():
    return datetime.now(timezone.utc).isoformat()


def _gen_id():
    return uuid.uuid4().hex[:12]


async def init_db():
    """Initialize database, create tables, seed if empty."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    async with aiosqlite.connect(DB_PATH) as db:
        await db.executescript(SCHEMA)
        cursor = await db.execute("SELECT COUNT(*) FROM projects")
        count = (await cursor.fetchone())[0]
        if count == 0:
            now = _now()
            for seed in SEEDS:
                await db.execute(
                    """INSERT INTO projects (id, name, status, track, domain, next_action,
                       mile, mile_total, today_time, last_touched, created_at, updated_at)
                       VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                    (*seed, now, now, now),
                )
            await db.commit()


async def get_db():
    """Get database connection."""
    return await aiosqlite.connect(DB_PATH)


# ─── Project CRUD ─────────────────────────────────────────────

def _row_to_dict(row, columns):
    return dict(zip(columns, row))


async def list_projects():
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = None
        cursor = await db.execute(
            "SELECT * FROM projects ORDER BY track, "
            "CASE status WHEN 'ACTIVE' THEN 1 WHEN 'ROLLING' THEN 2 "
            "WHEN 'BLOCKED' THEN 3 WHEN 'REVIEW' THEN 4 WHEN 'QUEUED' THEN 5 "
            "WHEN 'SHIPPED' THEN 6 END"
        )
        columns = [d[0] for d in cursor.description]
        rows = await cursor.fetchall()
        projects = [_row_to_dict(r, columns) for r in rows]

        # Attach logs to each project
        for p in projects:
            log_cursor = await db.execute(
                "SELECT text, created_at FROM logs WHERE project_id = ? ORDER BY created_at DESC LIMIT 10",
                (p["id"],),
            )
            p["log"] = [{"text": r[0], "at": r[1]} for r in await log_cursor.fetchall()]

        # Compute NEXT UP
        best_id = None
        best_score = -1
        for p in projects:
            if p["status"] in ("SHIPPED", "QUEUED"):
                continue
            score = 0
            if p["today_time"]:
                score += 100
            if p["status"] == "ACTIVE":
                score += 50
            elif p["status"] == "ROLLING":
                score += 40
            if p["track"] == "01":
                score += 30
            elif p["track"] == "02":
                score += 20
            elif p["track"] == "03":
                score += 10
            if p["last_touched"]:
                try:
                    days = (datetime.now(timezone.utc) - datetime.fromisoformat(p["last_touched"])).days
                    score += min(days * 3, 40)
                except (ValueError, TypeError):
                    pass
            if score > best_score:
                best_score = score
                best_id = p["id"]

        for p in projects:
            p["is_next_up"] = p["id"] == best_id
            # Convert snake_case to camelCase for frontend
            p["nextAction"] = p.pop("next_action", "")
            p["bgColor"] = p.pop("bg_color", "")
            p["mileTo"] = p.pop("mile_total", 0)
            p["todayTime"] = p.pop("today_time", "")
            p["lastTouched"] = p.pop("last_touched", "")
            p["createdAt"] = p.pop("created_at", "")
            p["updatedAt"] = p.pop("updated_at", "")
            p["isNextUp"] = p.pop("is_next_up", False)
            p["of"] = p.pop("mileTo", 0)
            # Keep history as empty list (computed from logs)
            p["history"] = []

        return projects


async def create_project(data: dict):
    now = _now()
    pid = data.get("id", _gen_id())
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """INSERT INTO projects (id, name, status, track, domain, next_action,
               deadline, bg_color, mile, mile_total, today_time, last_touched, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                pid,
                data.get("name", "New Project"),
                data.get("status", "QUEUED"),
                data.get("track", "03"),
                data.get("domain", "AI"),
                data.get("nextAction", data.get("next_action", "")),
                data.get("deadline", ""),
                data.get("bgColor", data.get("bg_color", "")),
                data.get("mile", 0),
                data.get("of", data.get("mile_total", 0)),
                data.get("todayTime", data.get("today_time", "")),
                now, now, now,
            ),
        )
        await db.commit()
    return {"id": pid}


async def update_project(pid: str, data: dict):
    now = _now()
    fields = []
    values = []
    field_map = {
        "name": "name", "status": "status", "track": "track", "domain": "domain",
        "nextAction": "next_action", "next_action": "next_action",
        "deadline": "deadline",
        "bgColor": "bg_color", "bg_color": "bg_color",
        "mile": "mile",
        "of": "mile_total", "mile_total": "mile_total",
        "todayTime": "today_time", "today_time": "today_time",
    }
    for key, col in field_map.items():
        if key in data:
            fields.append(f"{col} = ?")
            values.append(data[key])

    fields.append("updated_at = ?")
    values.append(now)
    fields.append("last_touched = ?")
    values.append(now)
    values.append(pid)

    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            f"UPDATE projects SET {', '.join(fields)} WHERE id = ?",
            values,
        )
        await db.commit()
    return {"id": pid, "updated": True}


async def delete_project(pid: str):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM logs WHERE project_id = ?", (pid,))
        await db.execute("DELETE FROM projects WHERE id = ?", (pid,))
        await db.commit()
    return {"id": pid, "deleted": True}


async def add_log(pid: str, text: str):
    now = _now()
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO logs (project_id, text, created_at) VALUES (?, ?, ?)",
            (pid, text, now),
        )
        await db.execute(
            "UPDATE projects SET last_touched = ?, updated_at = ? WHERE id = ?",
            (now, now, pid),
        )
        await db.commit()
    return {"project_id": pid, "text": text, "at": now}


async def get_recap():
    """Generate today's recap."""
    today = datetime.now(timezone.utc).date().isoformat()
    async with aiosqlite.connect(DB_PATH) as db:
        cursor = await db.execute(
            "SELECT id, name, status FROM projects WHERE date(last_touched) = date(?)",
            (today,),
        )
        touched = [{"id": r[0], "name": r[1], "status": r[2]} for r in await cursor.fetchall()]

        log_cursor = await db.execute(
            "SELECT COUNT(*) FROM logs WHERE date(created_at) = date(?)",
            (today,),
        )
        log_count = (await log_cursor.fetchone())[0]

    return {
        "date": today,
        "projectsTouched": len(touched),
        "projects": touched,
        "logEntries": log_count,
    }
