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
from pathlib import Path

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
    click.echo(f"  {DIM}→ Backups: {db.backup_dir()}  (each day it changes, newest {db.BACKUP_DAYS} kept){RESET}")
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


_COUNT_LABELS = {"projects": "projects", "notes": "notes", "logs": "log entries",
                 "events": "events", "viewers": "viewer links"}


def _describe(counts: dict) -> str:
    """'projects: 14 · notes: 1 · ...' with '?' for a table that can't be read."""
    return " · ".join(f"{_COUNT_LABELS[t]}: {'?' if n is None else n}" for t, n in counts.items())


@cli.command()
@click.option("--yes", "-y", is_flag=True, help="Skip the confirmation prompt.")
@click.option("--port", type=int, default=None,
              help="Port the board runs on, if not 4040 (seed won't run while it's up).")
@click.pass_context
def seed(ctx, yes: bool, port: int | None) -> None:
    """Replace the board with the demo projects (saves a backup first)."""
    from departures import db

    if port is None:  # `departures --port N seed` names the port up front
        port = ctx.parent.params.get("port", 4040)
    _refuse_if_running(port)  # an open board would keep showing the old projects

    counts = db.board_counts()
    if counts and not yes:
        click.echo(f"{AMBER}This erases everything on the board at{RESET}")
        click.echo(f"  {WHITE}{db.DB_PATH}{RESET}")
        click.echo(f"  {DIM}{_describe(counts)}{RESET}")
        click.echo(f"{AMBER}and replaces it with the {len(db.SEEDS)} demo projects. "
                   f"A backup is saved first.{RESET}")
        click.confirm("Continue?", abort=True)

    click.echo(f"{AMBER}Seeding database...{RESET}")
    try:
        backup = asyncio.run(db.seed_db())
    except db.BackupTimeout as exc:
        raise click.ClickException(
            f"Couldn't back up the board first: {exc}. Nothing was changed. "
            "Is another program holding the board open?"
        ) from exc
    if backup:
        click.echo(f"{WHITE}Backup saved:{RESET} {backup}")
    click.echo(f"{WHITE}Done. Database reset to seed data.{RESET}")


def _links_coming_back(staged: Path) -> list[str]:
    """Emails on viewer links the backup has and the current board doesn't:
    links removed since the backup was taken would work again."""
    from departures import db

    if not db.DB_PATH.exists():
        return []
    incoming = db.viewer_links(staged) or {}
    current = db.viewer_links() or {}  # unreadable now: every link in the backup counts
    return sorted({email for token, email in incoming.items() if token not in current})


def _warn_links(emails: list[str], restored: bool) -> None:
    if restored:
        click.echo(f"{AMBER}Viewer links that came back with the backup:{RESET} {', '.join(emails)}")
    else:
        click.echo(f"{AMBER}Viewer links in the backup that aren't on the board now:{RESET} {', '.join(emails)}")
    lead = "They work again" if restored else "Restoring brings them back"
    click.echo(f"{AMBER}{lead}: anyone holding one can view the board while it's shared on "
               f"your network. Remove any you don't want in the board's Share panel.{RESET}")


def _before_restore_files() -> set[Path]:
    """The before-restore copies already in the backups folder."""
    from departures import db

    folder = db.backup_dir()
    return set(folder.glob("*-before-restore*")) if folder.is_dir() else set()


def _new_kept(before: set[Path]) -> list[Path]:
    """The before-restore files a restore just wrote, the main copy first.
    A restore cut short after the swap can't hand its list back, so it's
    read off the folder instead of guessed."""
    files = _before_restore_files() - before
    return sorted(files, key=lambda p: (not p.name.endswith(".db"), p.name))


_COMPLETE_COPY_CLAIM = ". A complete copy of it is kept at "


def _restore_failure_message(exc: Exception, board_was_missing: bool,
                             kept_now: list[Path]) -> str:
    """install_restore's message promises "a complete copy" of the board.
    With no board there was never a complete copy, only leftover working
    files beside where it was: say what is actually kept, each by name."""
    from departures import db

    text = str(exc)
    if not board_was_missing or _COMPLETE_COPY_CLAIM not in text:
        return text
    before = text.split(_COMPLETE_COPY_CLAIM, 1)[0]
    if not kept_now:
        return (f"{before} There was no board to keep, and its leftover working "
                f"files couldn't be kept either.")
    names = ", ".join(p.name for p in kept_now)
    return (f"{before} There was no board to keep, only leftover working files beside "
            f"where it was; those are kept in {db.backup_dir()}: {names}.")


def _refuse_if_running(port: int) -> None:
    if _board_already_running(port):
        raise click.ClickException(
            f"The board is running on port {port}. Stop it first (Ctrl+C in its "
            "window; if the silent launcher started it, end its python.exe in "
            "Task Manager), then run this again."
        )


@cli.command()
@click.argument("backup", required=False)
@click.option("--yes", "-y", is_flag=True, help="Skip the confirmation prompt.")
@click.option("--port", type=int, default=None,
              help="Port the board runs on, if not 4040 (restore won't run while it's up).")
@click.pass_context
def restore(ctx, backup: str | None, yes: bool, port: int | None) -> None:
    """Put a backup back as the board. With no BACKUP, list the backups.

    BACKUP is a file name from the backups folder, or a path to a file.
    The current board is kept in the backups folder, so a restore can be
    undone by restoring that.
    """
    from departures import db

    if port is None:  # `departures --port N restore ...` names the port up front
        port = ctx.parent.params.get("port", 4040)

    if not backup:
        found = db.list_backups()
        if not found:
            click.echo(f"{DIM}No backups yet in {db.backup_dir()}{RESET}")
            return
        click.echo(f"{WHITE}Backups in {db.backup_dir()}, newest first:{RESET}")
        for path in found:
            click.echo(f"  {path.name}")
        click.echo(f"{DIM}Restore one with: departures restore <name>{RESET}")
        return

    _refuse_if_running(port)

    source = Path(backup)
    if not source.exists() and (db.backup_dir() / backup).is_file():
        source = db.backup_dir() / backup
    try:
        staged, incoming = db.stage_restore(source)
    except db.RestoreError as exc:
        raise click.ClickException(str(exc)) from exc

    installed = False
    interrupted = False
    kept: list[Path] = []
    try:
        returning = _links_coming_back(staged)
        if not yes:
            current = db.board_counts()
            click.echo(f"{AMBER}This replaces the board at{RESET}")
            click.echo(f"  {WHITE}{db.DB_PATH}{RESET}")
            if current:
                click.echo(f"  {DIM}now:    {_describe(current)}{RESET}")
            click.echo(f"{AMBER}with the backup{RESET}")
            click.echo(f"  {WHITE}{source}{RESET}")
            click.echo(f"  {DIM}backup: {_describe(incoming)}{RESET}")
            if returning:
                _warn_links(returning, restored=False)
            if current:
                click.echo(f"{AMBER}The current board is kept in the backups folder, "
                           f"so this can be undone.{RESET}")
            click.confirm("Continue?", abort=True)
            _refuse_if_running(port)  # it may have been started while the question waited
        board_was_missing = not db.DB_PATH.exists()
        staged_id = db._file_identity(staged)
        kept_before = _before_restore_files()
        try:
            kept = db.install_restore(staged)
            installed = True
        except db.RestoreError as exc:
            if db._file_identity(db.DB_PATH) != staged_id:
                raise click.ClickException(
                    _restore_failure_message(exc, board_was_missing,
                                             _new_kept(kept_before))
                ) from exc
            # The rename landed; only install_restore's own report was cut short.
        except KeyboardInterrupt:
            if db._file_identity(db.DB_PATH) != staged_id:
                raise  # nothing was replaced: let the interrupt stop the command
            interrupted = True
            kept = _new_kept(kept_before)  # install_restore couldn't hand its list back
    finally:
        if not installed:
            db.discard_restore(staged)  # already renamed away after the swap; harmless

    if interrupted:
        click.echo(f"{AMBER}Ctrl+C came after the board was replaced; the restore is complete.{RESET}")
    try:
        click.echo(f"{WHITE}Restored:{RESET} {_describe(db.board_counts())}")
        if kept:
            whole = kept[0].name.endswith(".db")
            label = "Previous board kept at:" if whole else "Leftover files of a missing board kept at:"
            click.echo(f"{WHITE}{label}{RESET} {kept[0]}")
            for extra in kept[1:]:
                click.echo(f"  {DIM}with {extra.name}{RESET}")
        if returning and (yes or interrupted):
            _warn_links(returning, restored=True)
        click.echo(f"{DIM}Start the board with: departures{RESET}")
    except KeyboardInterrupt:
        click.echo(f"{AMBER}Ctrl+C came after the board was replaced; the restore is complete.{RESET}")


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
