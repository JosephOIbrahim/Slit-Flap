"""
DEPARTURES CLI — starts the server, opens the browser, prints the banner.

Entry point: `departures` command (via pyproject.toml console_scripts).
"""

import io
import sys

# Force UTF-8 stdout on Windows before any print
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(
        sys.stdout.buffer, encoding="utf-8", errors="replace"
    )

import asyncio
import json
import threading
import time
import urllib.request
import webbrowser

import click

from departures import __version__

# ── ANSI Colors ──────────────────────────────────────────────────
AMBER = "\033[38;2;212;160;18m"
DIM = "\033[38;2;60;60;60m"
WHITE = "\033[38;2;232;228;222m"
RESET = "\033[0m"

# ── Banner ───────────────────────────────────────────────────────
BANNER = f"""{AMBER}
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║   ┌─┐┌─┐┌─┐┌─┐┌─┐┌─┐┌─┐┌─┐┌─┐┌─┐┌─┐                  ║
║   │D││E││P││A││R││T││U││R││E││S││ │                  ║
║   └─┘└─┘└─┘└─┘└─┘└─┘└─┘└─┘└─┘└─┘└─┘                  ║
║                                                          ║
║   USD-COMPOSED PROJECT STATE                             ║
║   SOLARI PROTOCOL v{__version__:<38}║
║                                                          ║
╚══════════════════════════════════════════════════════════╝{RESET}
"""


def _open_browser(port: int, delay: float = 1.5) -> None:
    """Open the board in the default browser after a short delay."""
    time.sleep(delay)
    webbrowser.open(f"http://localhost:{port}")


def _board_already_running(port: int) -> bool:
    """True if a DEPARTURES server is already answering on this port."""
    try:
        with urllib.request.urlopen(f"http://localhost:{port}/api/session", timeout=1) as r:
            return "startedAt" in json.loads(r.read())
    except Exception:
        return False


@click.group(invoke_without_command=True)
@click.version_option(__version__, prog_name="departures")
@click.option("--port", default=4040, show_default=True, help="Port to run the server on.")
@click.option("--host", default="127.0.0.1", show_default=True, help="Host to bind to. Use 0.0.0.0 for network sharing.")
@click.option("--no-browser", is_flag=True, default=False, help="Start server without opening the browser.")
@click.pass_context
def cli(ctx, port: int, host: str, no_browser: bool) -> None:
    """DEPARTURES — a project manager that looks like a departure board."""
    if ctx.invoked_subcommand is not None:
        return

    # ── Already departed? Just open the board ────────────────────
    if _board_already_running(port):
        click.echo(f"  {AMBER}Board already departed on port {port}.{RESET}")
        if not no_browser:
            click.echo(f"  {WHITE}→ Opening in browser...{RESET}")
            webbrowser.open(f"http://localhost:{port}")
        return

    # ── Print startup info ───────────────────────────────────────
    click.echo(BANNER)
    click.echo(f"  {WHITE}→ Server:{RESET}  http://localhost:{port}")
    if host == "0.0.0.0":
        import socket
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            s.connect(("8.8.8.8", 80))
            lan_ip = s.getsockname()[0]
            s.close()
        except Exception:
            lan_ip = "YOUR-IP"
        click.echo(f"  {WHITE}→ Share:{RESET}   http://{lan_ip}:{port}")
        click.echo(f"  {DIM}  Add viewers in the board's Share panel{RESET}")
    if no_browser:
        click.echo(f"  {DIM}→ Board:   --no-browser{RESET}")
    else:
        click.echo(f"  {WHITE}→ Board:{RESET}   Opening in browser...")
    from departures import db
    click.echo(f"  {DIM}→ Data:    {db.DB_PATH}{RESET}")
    click.echo(f"  {DIM}→ Backups: {db.backup_dir()}  (daily, newest {db.BACKUP_DAYS} kept){RESET}")
    click.echo(f"  {DIM}→ Press Ctrl+C to stop{RESET}")
    click.echo()

    # ── Open browser in daemon thread ────────────────────────────
    if not no_browser:
        t = threading.Thread(target=_open_browser, args=(port,), daemon=True)
        t.start()

    # ── Start uvicorn ────────────────────────────────────────────
    try:
        import uvicorn

        uvicorn.run(
            "departures.server:app",
            host=host,
            port=port,
            log_level="warning",
        )
    except KeyboardInterrupt:
        pass
    finally:
        click.echo(f"\n  {DIM}Server stopped.{RESET}")


@cli.command()
@click.option("--yes", "-y", is_flag=True, help="Skip the confirmation prompt.")
def seed(yes: bool) -> None:
    """Replace the board with the demo projects (saves a backup first)."""
    from departures import db

    counts = db.board_counts()
    if counts and not yes:
        labels = {"projects": "projects", "notes": "notes", "logs": "log entries",
                  "events": "events", "viewers": "viewer links"}
        erased = " · ".join(f"{labels[t]}: {n}" for t, n in counts.items())
        click.echo(f"{AMBER}This erases everything on the board at{RESET}")
        click.echo(f"  {WHITE}{db.DB_PATH}{RESET}")
        click.echo(f"  {DIM}{erased}{RESET}")
        click.echo(f"{AMBER}and replaces it with the {len(db.SEEDS)} demo projects. "
                   f"A backup is saved first.{RESET}")
        click.confirm("Continue?", abort=True)

    click.echo(f"{AMBER}Seeding database...{RESET}")
    backup = asyncio.run(db.seed_db())
    if backup:
        click.echo(f"{WHITE}Backup saved:{RESET} {backup}")
    click.echo(f"{WHITE}Done. Database reset to seed data.{RESET}")


@cli.command()
def recap() -> None:
    """Print today's recap to the terminal in Solari style."""
    from departures import db

    data = asyncio.run(db.get_recap())

    projects_touched = data.get("projects", [])
    log_count = data.get("logEntries", 0)

    # ── Build recap box ──────────────────────────────────────────
    click.echo()
    click.echo(f"{AMBER}╔══════════════════════════════════════════╗{RESET}")
    click.echo(f"{AMBER}║  {WHITE}TODAY'S RECAP{AMBER}                           ║{RESET}")
    click.echo(f"{AMBER}╠══════════════════════════════════════════╣{RESET}")
    click.echo(f"{AMBER}║  {DIM}TOUCHED:{RESET}  {WHITE}{len(projects_touched):<30}{AMBER}║{RESET}")
    click.echo(f"{AMBER}║  {DIM}LOG ENTRIES:{RESET}  {WHITE}{log_count:<26}{AMBER}║{RESET}")
    click.echo(f"{AMBER}╠══════════════════════════════════════════╣{RESET}")

    if projects_touched:
        for proj in projects_touched:
            name = proj.get("name", "UNKNOWN")
            status = proj.get("status", "—")
            line = f"  {name}  ·  {status}"
            # Pad to fill the box width (40 inner chars)
            padded = f"{line:<40}"
            click.echo(f"{AMBER}║{WHITE}{padded}{AMBER}║{RESET}")
    else:
        click.echo(f"{AMBER}║  {DIM}No projects touched today.{RESET}              {AMBER}║{RESET}")

    click.echo(f"{AMBER}╚══════════════════════════════════════════╝{RESET}")
    click.echo()


def main() -> None:
    """Entry point for the `departures` console script."""
    try:
        cli()
    except KeyboardInterrupt:
        pass
