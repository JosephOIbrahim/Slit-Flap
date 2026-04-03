# DEPARTURES

```
  ╔═══╗ ╔═══╗ ╔═══╗ ╔═══╗ ╔═══╗ ╔═══╗ ╔═══╗ ╔═══╗ ╔═══╗ ╔═══╗
  ║ D ║ ║ E ║ ║ P ║ ║ A ║ ║ R ║ ║ T ║ ║ U ║ ║ R ║ ║ E ║ ║ S ║
  ╚═══╝ ╚═══╝ ╚═══╝ ╚═══╝ ╚═══╝ ╚═══╝ ╚═══╝ ╚═══╝ ╚═══╝ ╚═══╝
```

**A project manager that looks like a train station departure board.**

One command. Browser opens. Your projects flip in like arrivals.

---

## Install

```bash
git clone https://github.com/JosephOIbrahim/departures.git
cd departures
pip install -e .
departures
```

That's it. Three commands. Browser opens. You're working.

---

## What It Looks Like

Each project is a split-flap departure card. Physical character modules with horizontal split lines through the letterforms. Dark panels. Amber accents. The names flip when things change.

Projects have two sides — **front** for status and tracking, **back** for sticky notes. Tap the flip icon to turn the card over.

---

## What It Does

**TODAY view** — your day as a departure board. Projects with time blocked, calendar events, emails, all sorted by time. A NOW line shows where you are.

**NEXT UP** — the board picks your next project based on priority, staleness, and what's scheduled. Amber border. You can override it. But it has an opinion so you don't have to decide.

**Session Pulse** — a small dot in the header. Green under 2 hours. Amber at 2-4. Red at 4+. It doesn't nag. It's just there.

**Daily Recap** — tap REC. See what you touched today, what shipped, how long you worked. Evidence of progress.

**Flip Notes** — every project card has a back side. Rich text notes. Like a sticky on the back of a departure card.

---

## For Artists & Creative Directors

This isn't a developer tool wearing a design skin. It was designed by a creative director with 16 years in VFX who has ADHD and needed a project manager that respects how his brain works.

The split-flap aesthetic isn't decoration — it's the metaphor. You glance up at the board and know where everything stands. Like walking into Penn Station and checking the departures.

**Design DNA:** Pentagram studio. Solari di Udine. 30th Street Station, Philadelphia.

---

## Tech

Python backend (FastAPI + SQLite). React frontend (Vite). Runs locally. Data stays on your machine. No cloud. No accounts. No subscriptions.

Future: USD composition layer for project state. Calendar and email integration. Harlo cognitive twin connection.

---

## Requirements

- Python 3.11+
- Node 18+ (for building the frontend)
- A browser

---

## Commands

| Command | What it does |
|---------|-------------|
| `departures` | Start the board (opens browser) |
| `departures --port 9000` | Use a custom port |
| `departures --no-browser` | Start without opening browser |
| `departures seed` | Reset to default projects |
| `departures recap` | Print today's recap in terminal |

---

## License

MIT

---

*USD-Composed Project State · Solari Protocol*
