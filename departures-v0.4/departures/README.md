# DEPARTURES

**USD-Composed Project State Board — Solari Protocol**

A CLI-launched project manager inspired by split-flap departure displays at train stations. Pentagram-principled typography. ADHD-native design. One command, browser opens, you're working.

## Quick Start

```bash
pip install -e .
departures
```

Browser opens at `http://localhost:4040`. That's it.

## Options

```bash
departures --port 8080        # custom port
departures --no-browser       # don't auto-open browser
departures --host 0.0.0.0     # expose to network (for phone access)
```

## Architecture

- **Backend**: FastAPI + SQLite (`~/.departures/departures.db`)
- **Frontend**: React (single HTML, served static)
- **CLI**: One command, starts server, opens browser

## Design Principles

- Two fonts: Disket Mono (display) + JetBrains Mono (system)
- One accent color: Amber `#d4a012`
- Split-flap character modules with horizontal slit through letterforms
- Hierarchy through scale: project names dominate, everything else whispers
- 18px vertical gutter between panels

## Features

- **TODAY view**: Unified timeline with projects, calendar events, emails
- **NEXT UP**: Board picks the highest-priority project for you
- **Session Pulse**: Ambient timer with color-coded duration
- **Last Touched**: Relative timestamps on every project
- **Session Log**: Timestamped notes per project
- **Daily Recap**: End-of-day summary of progress
- **Split-flap animation**: Characters flip on status change

## License

MIT
