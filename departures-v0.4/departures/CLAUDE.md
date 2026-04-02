# DEPARTURES

**CLI-launched project board inspired by Solari split-flap departure displays.**
**Pentagram-principled typography. USD-composed data model. ADHD-native design.**

## Architecture

```
departures/
├── departures/
│   ├── __init__.py
│   ├── __main__.py        ← `python -m departures` entry point
│   ├── cli.py             ← CLI launcher, opens browser, Solari banner
│   ├── server.py          ← FastAPI. Serves frontend + REST API
│   ├── db.py              ← SQLite via aiosqlite. 3 tables.
│   └── frontend/
│       └── dist/
│           └── index.html  ← Built React app (single HTML file)
├── pyproject.toml
├── CLAUDE.md
└── README.md
```

## Design Principles (DO NOT VIOLATE)

1. **Two fonts only**: Disket Mono (display/project names) + JetBrains Mono (system/utility)
2. **One accent color**: Amber `#d4a012` — nothing else gets color except BLOCKED (`#b04040`)
3. **Hierarchy through scale**: Project names are 104px split-flap modules. Everything else whispers at 7-10px.
4. **Split-flap modules**: Each character in its own physical housing with horizontal split line THROUGH the letterform
5. **Negative space is structure**: 18px gutter between panels, generous padding
6. **No decoration**: No gradients, no icons, no borders except structural dividers

## Tech Stack

- **Backend**: FastAPI + uvicorn + aiosqlite
- **Frontend**: React (compiled to single HTML file, served as static)
- **Database**: SQLite (`~/.departures/departures.db`)
- **CLI**: Click or argparse, opens browser via `webbrowser.open()`

## API Endpoints

```
GET    /api/projects          → list all projects (sorted by track, then status)
POST   /api/projects          → create project (returns created project)
PUT    /api/projects/{id}     → update project (partial update, returns updated)
DELETE /api/projects/{id}     → archive/delete project
POST   /api/projects/{id}/log → add log entry { text: string }
GET    /api/recap             → today's recap (projects touched, session duration)
GET    /api/session           → current session info (start time, duration)
GET    /                      → serves frontend/dist/index.html
GET    /static/*              → serves frontend static assets
```

## Database Schema

```sql
CREATE TABLE projects (
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

CREATE TABLE logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT REFERENCES projects(id) ON DELETE CASCADE,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    projects_touched TEXT DEFAULT '[]'
);
```

## Frontend ↔ Backend Contract

The React frontend uses `fetch('/api/...')` for all data operations. No `window.storage`.
All data is JSON. Project fields use snake_case in the API, camelCase in the frontend (the server handles mapping).

## Running

```bash
# Development
pip install -e ".[dev]"
departures                    # opens browser at http://localhost:4040

# Or directly
python -m departures
python -m departures --port 8080
python -m departures --no-browser
```

## Key Behaviors

- **Session tracking**: Server records session start on first request, tracks duration
- **Last touched**: Updated server-side on any PUT to a project
- **NEXT UP scoring**: Computed server-side, returned as `is_next_up: true` on one project
- **Daily recap**: Aggregated from session + project touch timestamps
- **Port**: Default 4040 (like a train platform number)

## What NOT to Build (v2)

- Google Calendar integration (needs OAuth)
- Gmail integration (needs MCP)
- Harlo/Cognitive Twin MCP connection
- PWA/service worker
- Multi-user / auth
- Deploy pipeline

## Commands for Claude Code

```bash
# Install dependencies
pip install fastapi uvicorn aiosqlite click --break-system-packages

# Run the server
cd departures && python -m departures

# Test the API
curl http://localhost:4040/api/projects
```
