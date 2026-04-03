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
import threading
import time
import webbrowser

import click

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
║   SOLARI PROTOCOL v0.4.0                                 ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝{RESET}
"""


def _open_browser(port: int, delay: float = 1.5) -> None:
    """Open the board in the default browser after a short delay."""
    time.sleep(delay)
    webbrowser.open(f"http://localhost:{port}")


@click.group(invoke_without_command=True)
@click.option("--port", default=4040, show_default=True, help="Port to run the server on.")
@click.option("--no-browser", is_flag=True, default=False, help="Start server without opening the browser.")
@click.pass_context
def cli(ctx, port: int, no_browser: bool) -> None:
    """DEPARTURES — a project manager that looks like a departure board."""
    if ctx.invoked_subcommand is not None:
        return

    # ── Print startup info ───────────────────────────────────────
    click.echo(BANNER)
    click.echo(f"  {WHITE}→ Server:{RESET}  http://localhost:{port}")
    if no_browser:
        click.echo(f"  {DIM}→ Board:   --no-browser{RESET}")
    else:
        click.echo(f"  {WHITE}→ Board:{RESET}   Opening in browser...")
    click.echo(f"  {DIM}→ Data:    ~/.departures/departures.db{RESET}")
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
            host="127.0.0.1",
            port=port,
            log_level="warning",
        )
    except KeyboardInterrupt:
        pass
    finally:
        click.echo(f"\n  {DIM}Server stopped.{RESET}")


@cli.command()
def seed() -> None:
    """Reset the database to seed data."""
    from departures import db

    click.echo(f"{AMBER}Seeding database...{RESET}")
    asyncio.run(db.seed_db())
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
