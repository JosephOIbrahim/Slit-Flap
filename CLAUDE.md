# CLAUDE.md — DEPARTURES

## What Is This

**DEPARTURES** is a project manager that looks and feels like a train station split-flap departure board. One CLI command opens a browser. Your projects flip in like arrivals at Penn Station. You check it on your phone, your desktop, your laptop — anywhere.

This is not a todo app. It's a **war room for a creative director running 16+ projects across VFX, AI, and web — who has ADHD and needs the board to have opinions, not just lists.**

```
  ╔═══╗ ╔═══╗ ╔═══╗ ╔═══╗ ╔═══╗ ╔═══╗ ╔═══╗ ╔═══╗ ╔═══╗ ╔═══╗
  ║ D ║ ║ E ║ ║ P ║ ║ A ║ ║ R ║ ║ T ║ ║ U ║ ║ R ║ ║ E ║ ║ S ║
  ╚═══╝ ╚═══╝ ╚═══╝ ╚═══╝ ╚═══╝ ╚═══╝ ╚═══╝ ╚═══╝ ╚═══╝ ╚═══╝
```

---

## Quick Start (The Only Thing That Matters)

```bash
git clone <repo-url> && cd departures
pip install -e .
departures
```

Browser opens. Board loads. You're working.

That's it. If it takes more than 3 commands, we failed.

---

## The Vibe

**Design DNA:** Pentagram studio restraint. Solari di Udine split-flap boards. The 30th Street Station departure board in Philadelphia. One font system (Disket Mono + JetBrains Mono). One accent color (amber). Typography IS the design.

**Aesthetic Rules:**
- Two fonts only. **Disket Mono** = identity (project names, headers). **JetBrains Mono** = system (everything else).
- One accent: amber `#d4a012`. Everything else is shades of grey.
- Each project name rendered as physical split-flap character modules with horizontal split lines through the letterforms
- Hierarchy through **scale alone**. Project names are massive. Everything else whispers.
- Dark background `#141414`. Panels `#1a1a1a`. Gutters visible between panels (18px).
- Animations: vertical flip (rotateX perspective) on actions. Cascade arrival on filter change.

**Reference prototype:** `frontend/src/App.jsx` — this is the working artifact built during design exploration. It IS the frontend. Port it, don't redesign it.

---

## Architecture

```
departures/
├── CLAUDE.md                ← You are here
├── README.md                ← Artist-friendly install + overview
├── pyproject.toml           ← `pip install -e .` → `departures` command
│
├── departures/              ← Python package
│   ├── __init__.py
│   ├── __main__.py          ← `python -m departures` entry point
│   ├── cli.py               ← Starts server, opens browser, prints banner
│   ├── server.py            ← FastAPI. Serves frontend + REST API
│   ├── db.py                ← SQLite CRUD. Projects, logs, sessions
│   └── usd_stage.py         ← USD composition layer (optional, v2)
│
├── frontend/
│   ├── src/
│   │   └── App.jsx          ← The artifact (design reference + production code)
│   ├── index.html
│   ├── package.json
│   └── vite.config.js       ← Vite build → dist/
│
├── data/                    ← SQLite DB lives here (gitignored)
│   └── departures.db
│
└── stages/                  ← USD stage files (v2, gitignored)
    └── projects.usda
```

---

## MoE Agent Roles

This project is built by a team of expert agents. Each expert owns their domain. The **CONDUCTOR** orchestrates.

### 🎯 CONDUCTOR
**Role:** Orchestrate the build. Manage dependencies between experts. Ensure the pieces connect.

**Responsibilities:**
- Sequence the build: Backend first → Frontend port → CLI → Integration test
- Resolve conflicts between expert decisions
- Run the full integration test: `departures` command → browser → CRUD works
- Ensure no expert breaks another expert's work
- Final sign-off: does it feel like a departure board, or did we lose the soul?

**Decision authority:** Architecture, sequencing, conflict resolution.

---

### 🎨 FRONTEND ARTIST
**Role:** Own the visual board. Every pixel. Every animation. Every typographic decision.

**Responsibilities:**
- Port `frontend/src/App.jsx` from `window.storage` to `fetch('/api/...')` calls
- Preserve ALL visual design: split-flap modules, Disket Mono, animation cascade, hover lift, panel gutters, session pulse, NEXT UP treatment, shipped state
- Implement the **FLIP PANEL** feature (see spec below)
- Set up Vite build: `npm run build` → `frontend/dist/`
- Ensure mobile responsiveness (iPhone Safari is the primary mobile target)
- Test: does the board still feel like a Solari departure board after the port?

**Design constraints the artist must protect:**
- Disket Mono for project names rendered as individual split-flap character modules
- 3px dark split line through each character (z-index above text)
- Flip animation (rotateX perspective) on status change and panel expand
- 18px vertical gutters between panels
- One accent color: amber `#d4a012`
- Text brightness: `#c8c4bc` (warm off-white, not clinical)
- Hover: `scale(1.015) translateY(-3px)` with deep shadow
- Session pulse: green dot < 2h, amber 2-4h, red 4h+

**Tech:** React 18, Vite, Tailwind optional (current build uses inline styles — keep it unless there's a strong reason to migrate).

---

### 🔧 BACKEND ARCHITECT
**Role:** Own the data layer. API endpoints. Persistence. The plumbing that makes the board real.

**Responsibilities:**
- `db.py` — SQLite schema with 3 tables:

```sql
-- Projects
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

-- Logs (per-project session notes)
CREATE TABLE logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    project_id TEXT NOT NULL,
    text TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- Notes (flip-side rich text per project)
CREATE TABLE notes (
    project_id TEXT PRIMARY KEY,
    content TEXT DEFAULT '',
    updated_at TEXT,
    FOREIGN KEY (project_id) REFERENCES projects(id)
);

-- Sessions (for daily recap / allostatic tracking)
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at TEXT NOT NULL,
    ended_at TEXT,
    projects_touched TEXT DEFAULT '[]',
    summary TEXT DEFAULT ''
);
```

- `server.py` — FastAPI with these endpoints:

```
GET    /api/projects              → List all projects
POST   /api/projects              → Create project
PUT    /api/projects/{id}         → Update project
DELETE /api/projects/{id}         → Delete project

GET    /api/projects/{id}/logs    → Get project logs
POST   /api/projects/{id}/logs    → Add log entry

GET    /api/projects/{id}/notes   → Get flip-side notes
PUT    /api/projects/{id}/notes   → Update flip-side notes

GET    /api/recap                 → Daily recap (today's touched projects + session time)
POST   /api/session/start         → Register session start
PUT    /api/session/end           → Register session end
```

- Serve `frontend/dist/` as static files at `/`
- CORS configured for local development (Vite dev server on :5173)
- All timestamps ISO 8601
- Seed data on first run if DB is empty (the 16 projects from the prototype)

**Tech:** FastAPI, uvicorn, SQLite (aiosqlite for async), Pydantic models.

---

### 🏗️ USD ENGINEER
**Role:** Design the USD composition layer that can eventually replace/augment SQLite for project state.

**Phase 1 (current build):** SQLite is the primary store. USD is **optional and deferred.**

**Phase 2 (future):** Each project becomes a USD prim. Status transitions are time-sampled. History is sublayered. The stage file is human-readable, git-trackable, and composable with external cognitive state systems.

**Responsibilities (Phase 1 — design only, don't build yet):**
- Document the USD schema mapping in `docs/USD_SCHEMA.md`
- Map SQLite tables → USD prim hierarchy:
  ```
  /departures/
    /departures/projects/
      /departures/projects/otto_os     ← project prim
      /departures/projects/us_patents
    /departures/sessions/
      /departures/sessions/session_001
  ```
- Define how `status` maps to variant sets
- Define how `log` entries map to time-sampled attributes
- Define how `notes` (flip-side) map to customData
- Ensure the schema is compatible with `AIMemoryChunk` / `CognitiveObservation` patterns

**Phase 2 (future build):**
- `usd_stage.py` — read/write `.usda` files alongside SQLite
- Export: `departures export --format usda` → dumps current state as a USD stage
- Import: `departures import stage.usda` → loads a stage into SQLite
- Bi-directional sync between SQLite (fast CRUD) and USD (composable, human-readable)

**Tech:** pxr.Usd (Python 3.12), .usda text format, LIVRPS composition.

---

### 🖥️ CLI BUILDER
**Role:** Own the terminal experience. The command that starts everything.

**Responsibilities:**
- `cli.py` — the entry point:

```python
"""
  ╔═══╗ ╔═══╗ ╔═══╗ ╔═══╗ ╔═══╗ ╔═══╗ ╔═══╗ ╔═══╗ ╔═══╗ ╔═══╗
  ║ D ║ ║ E ║ ║ P ║ ║ A ║ ║ R ║ ║ T ║ ║ U ║ ║ R ║ ║ E ║ ║ S ║
  ╚═══╝ ╚═══╝ ╚═══╝ ╚═══╝ ╚═══╝ ╚═══╝ ╚═══╝ ╚═══╝ ╚═══╝ ╚═══╝

  v0.4.0 · USD-Composed Project State · Solari Protocol

  → Server:  http://localhost:8400
  → Board:   Opening in browser...
  → Data:    ./data/departures.db
  → Press Ctrl+C to stop
"""
```

- `__main__.py` — so `python -m departures` works
- `pyproject.toml` — so `pip install -e .` creates `departures` command
- Auto-open browser on start (webbrowser module)
- Port: 8400 (default), configurable via `--port`
- `--no-browser` flag for headless/server use
- `departures seed` — reset DB to seed data
- `departures recap` — print today's recap to terminal (Solari-style)

**Tech:** click or typer for CLI, uvicorn programmatic start.

---

## Feature Spec: FLIP PANEL 🔄

**What:** Each project panel is a card with two sides. The **front** shows the split-flap name, status, metadata, mile markers (everything we have now). The **back** shows a rich text notes area — like a sticky note attached to the back of the departure card.

**Interaction:**
- A subtle **flip icon** (↻ or similar) on the far right of the top whisper line
- Tap it → the entire panel does a **3D Y-axis flip** (rotateY 180°) revealing the back
- The back has:
  - Project name (small, at top, for orientation)
  - A **rich text area** — simple formatting: bold, italic, bullet lists, links
  - Auto-saves on blur or after 1s debounce
  - Dark background matching the panel, light text
- Tap the flip icon again (or a "back to board" button) → flips back to front

**Animation:**
```css
/* Front → Back */
transform: perspective(1200px) rotateY(180deg);
transition: transform 0.6s cubic-bezier(0.22, 1, 0.36, 1);

/* Back content is rotateY(180deg) to read correctly when flipped */
```

**Data:** Notes stored per-project in the `notes` table. Content is HTML string from contentEditable or a lightweight rich text approach. No heavy editor library — keep it simple like Apple Stickies.

**Visual design:**
- Back panel: slightly different background tint (maybe `#1d1a17` — warm dark)
- Notes text: `#999` in JetBrains Mono 12px
- Minimal chrome. The notes area IS the back. No frames, no toolbars except inline formatting.
- The flip should feel physical — like turning over an actual departure card

---

## Build Sequence

The CONDUCTOR should execute in this order:

```
PHASE 1 — FOUNDATION
  1. CLI BUILDER    → pyproject.toml, __main__.py, cli.py (skeleton)
  2. BACKEND        → db.py (schema + seed), server.py (all endpoints)
  3. Integration    → `departures` starts, API responds, seed data loads

PHASE 2 — FRONTEND PORT
  4. FRONTEND       → Set up Vite project, copy artifact JSX
  5. FRONTEND       → Replace window.storage → fetch() calls
  6. FRONTEND       → Implement FLIP PANEL feature
  7. FRONTEND       → Build: npm run build → dist/
  8. BACKEND        → Serve dist/ from FastAPI
  9. Integration    → Full loop: CLI → server → browser → CRUD → persistence

PHASE 3 — POLISH
  10. FRONTEND      → Test mobile (responsive, touch targets)
  11. CLI BUILDER   → `departures seed`, `departures recap` commands
  12. USD ENGINEER  → Write docs/USD_SCHEMA.md (design only)
  13. ALL           → README.md, final integration test
```

---

## What We're NOT Building (Yet)

These are v2. Don't touch them. Don't scaffold them. Don't even create empty files for them.

- Google Calendar integration
- Gmail / email integration  
- Cognitive twin MCP connection
- User authentication
- Multi-user support
- Deployment / hosting
- Electron wrapper
- iOS/Android native
- Real USD read/write (Phase 1 is SQLite only)

---

## Tech Stack

| Layer | Tech | Why |
|-------|------|-----|
| Frontend | React 18 + Vite | Fast build, hot reload, artifact is already React |
| Styling | Inline styles | Current artifact uses them. Don't migrate unless painful. |
| Display font | Disket Mono (CDN) | Geometric monospace. Train station DNA. |
| System font | JetBrains Mono (Google Fonts) | Clean, readable, monospace utility. |
| Backend | FastAPI + uvicorn | Async, fast, minimal boilerplate. |
| Database | SQLite (aiosqlite) | Zero config. File-based. Portable. |
| CLI | click or typer | Simple arg parsing. |
| Build | Vite → static dist/ | FastAPI serves the built files. |
| Future | pxr.Usd (Python 3.12) | USD composition for project state. Deferred. |

---

## Environment

- **Python:** 3.11+ (3.12 if USD is needed later)
- **Node:** 18+ (for Vite frontend build)
- **OS:** Windows, macOS, Linux, WSL (must work on all — the user switches constantly)
- **Port:** 8400 (default)
- **Data dir:** `./data/` (created on first run)

---

## Testing Checklist

Before shipping, every one of these must work:

- [ ] `pip install -e .` succeeds
- [ ] `departures` starts server and opens browser
- [ ] Board loads with 16 seed projects on first run
- [ ] Default view is TODAY with mock calendar events and emails
- [ ] Projects have split-flap character modules with visible split lines
- [ ] Flip animation fires on status cycle and panel expand
- [ ] NEXT UP project has amber left border
- [ ] Session pulse shows in header with color transitions
- [ ] Clicking REC shows daily recap overlay
- [ ] Flip panel: tap icon → card flips → notes area → tap back → flips to front
- [ ] Notes auto-save and persist across page reload
- [ ] Logs (front side) persist across page reload
- [ ] Status changes persist across page reload
- [ ] Color picker changes persist across page reload
- [ ] Mobile: board is usable on iPhone Safari
- [ ] `Ctrl+C` cleanly stops the server
- [ ] `departures --port 9000` uses custom port
- [ ] `departures seed` resets to seed data

---

## The Soul of the Project

This board exists because its creator runs 16 projects across VFX, AI, and web development. He has ADHD. He switches between iOS, macOS, Windows, and WSL daily. Every existing project manager shows him a list and says "pick" — which is the worst possible UX for his brain.

DEPARTURES has opinions. It tells you what to work on next. It shows you where you left off. It notices when you've been going too long. It captures evidence of progress so the imposter voice has data to argue with.

The split-flap aesthetic isn't decoration. It's the metaphor. Projects are trains. They arrive, they depart, they have tracks and schedules. You glance up at the board and know where everything stands. That feeling — the certainty of a train station board — is what this project delivers.

Protect that feeling in every line of code.
