"""DEPARTURES — SQLite data layer (aiosqlite)."""

import asyncio
import hashlib
import logging
import os
import secrets
import shutil
import sqlite3
import tempfile
import time
import uuid
from contextlib import asynccontextmanager, closing
from datetime import date, datetime, timezone
from pathlib import Path

import aiosqlite

# DEPARTURES_HOME overrides the data dir (isolated boards, tests)
DB_DIR = Path(os.environ.get("DEPARTURES_HOME", str(Path.home() / ".departures")))
DB_PATH = DB_DIR / "departures.db"

log = logging.getLogger("uvicorn.error")  # the board's own terminal (and launcher.log)


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    return hex(int(datetime.now(timezone.utc).timestamp() * 1000))[2:] + uuid.uuid4().hex[:6]


@asynccontextmanager
async def _db(timeout: float = 5.0):
    """A connection to the board. `timeout`: seconds to wait for a lock."""
    DB_DIR.mkdir(parents=True, exist_ok=True)
    db = await aiosqlite.connect(str(DB_PATH), timeout=timeout)
    try:
        await db.execute("PRAGMA journal_mode=WAL")
        await db.execute("PRAGMA foreign_keys=ON")
        db.row_factory = aiosqlite.Row
        yield db
    finally:
        await db.close()


# ── Table specs (column ↔ camelCase mapping + generic CRUD) ──────


class _Table:
    """Maps snake_case columns to the camelCase keys the frontend speaks."""

    def __init__(self, name: str, cols: list[str], camel: dict[str, str]):
        self.name = name
        self.cols = cols
        self._to_camel = camel
        self._to_col = {v: k for k, v in camel.items()}

    def row_out(self, row) -> dict:
        return {self._to_camel.get(c, c): row[c] for c in self.cols}

    def col(self, key: str) -> str:
        return self._to_col.get(key, key)

    async def insert(self, db, vals: dict) -> None:
        cols = ", ".join(vals.keys())
        placeholders = ", ".join("?" for _ in vals)
        await db.execute(
            f"INSERT INTO {self.name} ({cols}) VALUES ({placeholders})",
            tuple(vals.values()),
        )

    async def update(self, db, row_id: str, data: dict, touch: tuple[str, ...]) -> None:
        """Partial update from camelCase data. `touch` columns get stamped
        with now unless the caller supplied them explicitly."""
        sets, params = [], []
        for key, value in data.items():
            col = self.col(key)
            if col in self.cols and col not in ("id", "created_at"):
                sets.append(f"{col} = ?")
                params.append(value)
        now = _now()
        present = {s.split(" = ")[0] for s in sets}
        for col in touch:
            if col not in present:
                sets.append(f"{col} = ?")
                params.append(now)
        params.append(row_id)
        await db.execute(f"UPDATE {self.name} SET {', '.join(sets)} WHERE id = ?", params)


PROJECTS = _Table(
    "projects",
    ["id", "name", "status", "track", "domain", "next_action",
     "deadline", "bg_color", "mile", "mile_total", "today_time",
     "sort_order", "last_touched", "created_at", "updated_at"],
    {"next_action": "next", "bg_color": "bgColor", "mile_total": "of",
     "today_time": "todayTime", "sort_order": "sortOrder",
     "last_touched": "lastTouched", "created_at": "createdAt", "updated_at": "updatedAt"},
)

EVENTS = _Table(
    "events",
    ["id", "time", "end_time", "name", "source", "linked_project", "created_at", "updated_at"],
    {"end_time": "endTime", "linked_project": "linkedProject",
     "created_at": "createdAt", "updated_at": "updatedAt"},
)


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

_SEED_SETTINGS = [("zip", ""), ("fontSize", "104"), ("alignment", "left")]


async def _seed_events_settings(db) -> None:
    now_str = _now()
    for eid, time, end_time, name, source, linked in SEED_EVENTS:
        await db.execute(
            "INSERT OR IGNORE INTO events (id, time, end_time, name, source, linked_project, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (eid, time, end_time, name, source, linked, now_str, now_str),
        )
    for key, val in _SEED_SETTINGS:
        await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, val))


async def _insert_seeds(db) -> None:
    now = datetime.now(timezone.utc)
    for i, (sid, name, status, track, domain, next_action, mile, mile_total, today_time) in enumerate(SEEDS):
        age_days = _SEED_AGES.get(sid, 5)
        last_touched = datetime.fromtimestamp(
            now.timestamp() - age_days * 86400, tz=timezone.utc
        ).isoformat()
        await db.execute(
            """INSERT INTO projects
               (id, name, status, track, domain, next_action, deadline, bg_color,
                mile, mile_total, today_time, sort_order, last_touched, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, '', '', ?, ?, ?, ?, ?, ?, ?)""",
            (sid, name, status, track, domain, next_action,
             mile, mile_total, today_time, i, last_touched,
             "2026-02-21T00:00:00+00:00", now.isoformat()),
        )
    await _seed_events_settings(db)
    await db.commit()


# ── Backups ───────────────────────────────────────────────────────
#
# Plain copies of the board in <data dir>/backups/, made with SQLite's
# online backup API (safe while the server is writing). To restore one,
# stop the board and run `departures restore <backup>` (see Restore below).

BACKUP_DAYS = 14  # daily snapshots kept
BACKUP_TIME_LIMIT = 10.0  # seconds a backup waits for a locked board before giving up


class BackupTimeout(RuntimeError):
    """Another program kept the board locked, so the backup was skipped."""


class BackupCheckFailed(RuntimeError):
    """The copy failed SQLite's integrity check. A backup copies the board
    page for page, so the board itself is probably damaged."""


# Files SQLite keeps next to a database while it works. They belong to that
# exact database file: left beside a different one, SQLite replays them onto
# it and corrupts it.
_SIDECARS = ("-wal", "-shm", "-journal")


def backup_dir() -> Path:
    return DB_DIR / "backups"


def _sidecars(path: Path) -> list[Path]:
    return [path.with_name(path.name + suffix) for suffix in _SIDECARS]


def _remove_board_files(path: Path) -> None:
    for p in (path, *_sidecars(path)):
        p.unlink(missing_ok=True)


def _stamped(kind: str) -> Path:
    """A new, unused backups/departures-<date>-<time>-<kind>.db path."""
    backup_dir().mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d-%H%M%S")
    dest = backup_dir() / f"departures-{stamp}-{kind}.db"
    n = 2
    while dest.exists():
        dest = backup_dir() / f"departures-{stamp}-{kind}-{n}.db"
        n += 1
    return dest


def _snapshot(dest: Path, keep=None) -> Path | None:
    """Copy the live database to dest: verified, self-contained, atomic.

    With `keep`, the verified copy is first shown to keep(copy); if that
    says no, it's thrown away and None is returned.

    If another program keeps the board locked, SQLite's backup would wait
    forever (holding up startup, or the first request of the day). It gives
    up after BACKUP_TIME_LIMIT seconds instead and raises BackupTimeout.
    """
    dest.parent.mkdir(parents=True, exist_ok=True)
    partial = dest.with_name(dest.name + ".partial")
    partial.unlink(missing_ok=True)
    limit = BACKUP_TIME_LIMIT
    deadline = time.monotonic() + limit

    def give_up_if_still_locked(status, remaining, total):
        # Called after every backup step, including ones that found the
        # board locked; raising here aborts the backup.
        if status in (sqlite3.SQLITE_BUSY, sqlite3.SQLITE_LOCKED) and time.monotonic() >= deadline:
            raise BackupTimeout(f"the board stayed locked for {limit:g}s, so the backup was skipped")

    try:
        with closing(sqlite3.connect(DB_PATH, timeout=min(1.0, limit))) as src, \
                closing(sqlite3.connect(partial)) as out:
            try:
                src.backup(out, progress=give_up_if_still_locked)
                out.execute("PRAGMA journal_mode=DELETE")  # one file, no -wal sidecar
                verdict = out.execute("PRAGMA quick_check").fetchone()[0]
            except sqlite3.OperationalError:  # locked, disk full, can't open: not damage
                raise
            except sqlite3.DatabaseError as exc:  # too damaged to copy or check
                verdict = str(exc)
        if verdict != "ok":
            raise BackupCheckFailed(f"the copy failed its integrity check ({verdict})")
        if keep is not None and not keep(partial):
            partial.unlink()
            return None
        os.replace(partial, dest)
    except BaseException:
        partial.unlink(missing_ok=True)
        raise
    return dest


# Columns that record when someone looked, not what the board holds. A
# viewer's visit updates last_seen, and counting that as a change would make
# every day with a visitor look changed, so quiet days would never be skipped.
_NOT_CONTENT = {"viewers": {"last_seen"}}


def _fingerprint(path: Path) -> str | None:
    """A digest of what a board holds: its tables and every row, leaving out
    bookkeeping such as when a viewer last looked. Two files holding the same
    board get the same digest even when SQLite laid them out differently.
    None if unreadable."""
    digest = hashlib.sha256()
    try:
        with closing(sqlite3.connect(path)) as conn:
            conn.execute("PRAGMA query_only = ON")
            entries = sorted(conn.execute("SELECT type, name, tbl_name, sql FROM sqlite_master"),
                             key=repr)
            for entry in entries:
                digest.update(repr(entry).encode() + bytes([10]))
                kind, name = entry[0], entry[1]
                if kind == "table":
                    skip = _NOT_CONTENT.get(name, set())
                    cols = [c[1] for c in conn.execute(f'PRAGMA table_info("{name}")')
                            if c[1] not in skip]
                    picked = ", ".join('"' + c.replace('"', '""') + '"' for c in cols) or "NULL"
                    for row in sorted(repr(r) for r in conn.execute(f'SELECT {picked} FROM "{name}"')):
                        digest.update(row.encode() + bytes([10]))
    except sqlite3.DatabaseError:
        return None
    return digest.hexdigest()


def _same_board(copy: Path, other: Path | None) -> bool:
    if other is None:
        return False
    mine = _fingerprint(copy)
    return mine is not None and mine == _fingerprint(other)


def _prune(pattern: str, keep: int, newest_last, made: Path) -> None:
    """Delete all but the newest `keep` backups matching pattern.

    `made`, the copy just taken, is always one of the ones kept: if the PC's
    clock was set back (say, to 2020), its name sorts as the oldest, and it
    would otherwise be deleted the moment it was made, every day. An old copy
    that can't be deleted (open in another program) is left for next time.
    """
    others = sorted((p for p in backup_dir().glob(pattern) if p != made), key=newest_last)
    for old in others[:max(0, len(others) - (keep - 1))]:
        try:
            old.unlink(missing_ok=True)
        except OSError as exc:
            log.warning("DEPARTURES couldn't delete old backup %s: %s", old.name, exc)


_DAILY = "departures-????-??-??.db"


def last_daily_backup() -> Path | None:
    """The newest daily backup (by its date), or None."""
    return max(backup_dir().glob(_DAILY), key=lambda p: p.name, default=None)


def backup_daily(today: date) -> Path | None:
    """Snapshot the board once per day. Returns the new file, or None if
    there is no board yet, today's snapshot already exists, or nothing on
    the board changed since the last one. Skipping unchanged days means the
    14 copies kept hold 14 different versions of the board, so a mistake
    noticed weeks later can still be undone if the board sat untouched."""
    if not DB_PATH.exists():
        return None
    dest = backup_dir() / f"departures-{today.isoformat()}.db"
    if dest.exists():
        return None
    last = last_daily_backup()
    if _snapshot(dest, keep=lambda copy: not _same_board(copy, last)) is None:
        return None
    _prune(_DAILY, BACKUP_DAYS, newest_last=lambda p: p.name, made=dest)
    return dest


def backup_before_seed() -> Path | None:
    """Snapshot the board before a reset wipes it. These are never pruned:
    each one may be the only copy of a board someone reset by mistake."""
    if not DB_PATH.exists():
        return None
    return _snapshot(_stamped("before-seed"))


_COUNTED_TABLES = ("projects", "notes", "logs", "events", "viewers")


def board_counts(path: Path | None = None) -> dict[str, int | None]:
    """What a board holds, by table; empty if the file doesn't exist.

    Reads the main file only and never writes to the board (not even a
    pending -wal), so it's safe on a damaged board: None marks a table it
    couldn't read.
    """
    path = Path(path or DB_PATH)
    if not path.exists():
        return {}
    try:
        conn = sqlite3.connect(path.resolve().as_uri() + "?immutable=1", uri=True)
    except sqlite3.OperationalError:
        # SQLite can't open file: URIs for network shares (\\server\share\...).
        # Open the file directly instead, but a private copy of it: opened in
        # place, SQLite could fold the board's -wal into it just to count rows.
        return _counts_from_copy(path)
    with closing(conn):
        return _count_tables(conn)


def _counts_from_copy(path: Path) -> dict[str, int | None]:
    try:
        with tempfile.TemporaryDirectory(prefix="departures-counts-",
                                         ignore_cleanup_errors=True) as tmp:
            copy = Path(tmp) / "board.db"
            shutil.copyfile(path, copy)
            with closing(sqlite3.connect(copy)) as conn:
                return _count_tables(conn)
    except OSError:
        return {table: None for table in _COUNTED_TABLES}


def _count_tables(conn: sqlite3.Connection) -> dict[str, int | None]:
    counts: dict[str, int | None] = {}
    for table in _COUNTED_TABLES:
        try:
            counts[table] = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except sqlite3.OperationalError as exc:
            counts[table] = 0 if "no such table" in str(exc) else None
        except sqlite3.DatabaseError:
            counts[table] = None
    return counts


def _read_copy(path: Path, read):
    """read(conn) on a private copy of a board file and its -wal. The copy
    includes changes still in the -wal (after a crash), and the board's own
    files are never opened by SQLite, which could fold that -wal in."""
    with tempfile.TemporaryDirectory(prefix="departures-read-", ignore_cleanup_errors=True) as tmp:
        copy = Path(tmp) / "board.db"
        shutil.copyfile(path, copy)
        wal = path.with_name(path.name + "-wal")
        if wal.is_file():
            shutil.copyfile(wal, copy.with_name(copy.name + "-wal"))
        with closing(sqlite3.connect(copy)) as conn:
            return read(conn)


def viewer_links(path: Path | None = None) -> dict[str, str] | None:
    """The viewer links on a board, as {token: email}. {} for none (or no
    board), None if the board can't be read."""
    path = Path(path or DB_PATH)
    if not path.exists():
        return {}

    def read(conn):
        try:
            return dict(conn.execute("SELECT token, email FROM viewers"))
        except sqlite3.OperationalError as exc:
            if "no such table" in str(exc):
                return {}
            raise

    try:
        return _read_copy(path, read)
    except (OSError, sqlite3.DatabaseError):
        return None


# ── Restore ───────────────────────────────────────────────────────
#
# Two steps, so the CLI can show what's coming and ask first:
#   stage_restore(backup)   copy the backup in beside the board and check it
#   install_restore(staged) keep a copy of the current board in backups/,
#                           then swap the checked copy in with one rename


class RestoreError(Exception):
    """A restore didn't happen. The message says what, if anything, changed."""


# The columns the board reads. A table that's missing is created when the
# board starts; one that's there must have these (projects.sort_order is
# also added at start, so boards from before it still restore).
_BOARD_COLUMNS = {
    "projects": set(PROJECTS.cols) - {"sort_order"},
    "logs": {"id", "project_id", "text", "created_at"},
    "notes": {"project_id", "content", "updated_at"},
    "events": set(EVENTS.cols),
    "settings": {"key", "value"},
    "viewers": {"id", "email", "token", "created_at", "last_seen"},
}


def _not_a_board(conn: sqlite3.Connection) -> str | None:
    """Why a database can't run as a DEPARTURES board, or None if it can."""
    tables = {row[0] for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")}
    if "projects" not in tables:
        return "it has no projects table"
    for table, needed in _BOARD_COLUMNS.items():
        if table in tables:
            have = {row[1] for row in conn.execute(f"PRAGMA table_info({table})")}
            if missing := needed - have:
                return f"its {table} table has no {', '.join(sorted(missing))}"
    return None


def list_backups() -> list[Path]:
    """Every backup in the backups folder, newest first."""
    if not backup_dir().is_dir():
        return []
    found = [p for p in backup_dir().glob("departures-*.db") if p.is_file()]
    return sorted(found, key=lambda p: p.stat().st_mtime, reverse=True)


def stage_restore(backup: Path) -> tuple[Path, dict[str, int | None]]:
    """Copy a backup in beside the board as departures.db.restoring and
    prove it's a healthy board. Any -wal or -journal that came with the
    backup is folded in, leaving one clean file. The backup itself is only
    read. Returns (staged file, what it holds)."""
    backup = Path(backup)
    if not backup.is_file():
        raise RestoreError(f"There's no backup file at {backup}")
    if DB_PATH.exists() and backup.resolve() == DB_PATH.resolve():
        raise RestoreError("That's the live board itself, not a backup.")
    DB_DIR.mkdir(parents=True, exist_ok=True)
    staged = DB_PATH.with_name(DB_PATH.name + ".restoring")
    _remove_board_files(staged)
    try:
        shutil.copyfile(backup, staged)
        for suffix in ("-wal", "-journal"):
            travelling = backup.with_name(backup.name + suffix)
            if travelling.is_file():
                shutil.copyfile(travelling, staged.with_name(staged.name + suffix))
        with closing(sqlite3.connect(staged)) as conn:
            verdict = conn.execute("PRAGMA quick_check").fetchone()[0]
            if verdict != "ok":
                raise RestoreError(f"That backup is damaged ({verdict}).")
            if problem := _not_a_board(conn):
                raise RestoreError(f"That file isn't a DEPARTURES board ({problem}).")
            conn.execute("PRAGMA journal_mode=DELETE")  # fold any journal in
        for side in _sidecars(staged):
            side.unlink(missing_ok=True)
    except sqlite3.DatabaseError as exc:
        _remove_board_files(staged)
        raise RestoreError(f"That file isn't a readable board ({exc}).") from exc
    except BaseException:
        _remove_board_files(staged)
        raise
    return staged, board_counts(staged)


def discard_restore(staged: Path) -> None:
    """Throw away a staged restore that won't be installed."""
    _remove_board_files(staged)


def _keep_board(kept: Path) -> list[Path]:
    """Copy the current board into backups/ as `kept` before it's replaced:
    a verified single file with its -wal folded in, or, for a board too
    damaged to copy that way, its raw files (-wal and all), so nothing is
    lost. Leftover -wal/-shm with no board beside them are kept raw too.
    Returns the files written. Raises BackupTimeout if another program
    holds the board locked."""
    if DB_PATH.exists():
        try:
            return [_snapshot(kept)]
        except BackupCheckFailed:
            pass  # damaged: keep its files exactly as they are
    written: list[Path] = []
    try:
        for src in (DB_PATH, *_sidecars(DB_PATH)):
            if src.exists():
                dst = kept.with_name(kept.name + src.name[len(DB_PATH.name):])
                shutil.copyfile(src, dst)
                written.append(dst)
    except BaseException:
        for f in written:
            f.unlink(missing_ok=True)
        raise
    return written


def _fsync(path: Path) -> None:
    with open(path, "rb+") as f:
        os.fsync(f.fileno())


def _fsync_dir(folder: Path) -> None:
    """Make a rename in folder survive a power cut. (Windows can't open a
    folder for this; NTFS journals the rename itself.)"""
    if os.name == "nt":
        return
    fd = os.open(folder, os.O_RDONLY)
    try:
        os.fsync(fd)
    finally:
        os.close(fd)


def install_restore(staged: Path) -> list[Path]:
    """Swap a staged backup in as the board.

    1. Keep a copy of the current board in backups/ (see _keep_board).
    2. Clear the old board's -wal/-shm/-journal: left beside the restored
       file, SQLite would replay them onto it.
    3. Rename the staged file over departures.db, flushed to disk first.
       That rename is the one step that changes the board, so a restore
       cut short (Ctrl+C, a crash, a power cut) leaves the old board or
       the restored one: never a mix, and never no board at all.
    Returns the files the previous board was kept as, so the restore can
    be undone ([] if there was no board).
    """
    kept: list[Path] = []
    cleared = False  # one of the live board's leftover files was deleted
    try:
        if DB_PATH.exists() or any(side.exists() for side in _sidecars(DB_PATH)):
            kept = _keep_board(_stamped("before-restore"))
        for side in _sidecars(DB_PATH):
            if side.exists():
                side.unlink()
                cleared = True
        _fsync(staged)
        os.replace(staged, DB_PATH)
    except BaseException as exc:
        if not staged.exists():  # interrupted just after the rename: the restore is done
            raise
        discard_restore(staged)
        if not cleared:
            for f in kept:
                f.unlink(missing_ok=True)
        if not isinstance(exc, (OSError, sqlite3.Error, BackupTimeout)):
            raise
        if isinstance(exc, BackupTimeout):
            why = "another program has the board locked"
        else:
            why = getattr(exc, "strerror", None) or str(exc)
        if not cleared:
            raise RestoreError(
                f"Couldn't restore ({why}). Nothing was changed. "
                "If the board is running, stop it first."
            ) from exc
        raise RestoreError(
            f"Couldn't restore ({why}). The board wasn't replaced, but its leftover "
            f"working files were cleared. A complete copy of it is kept at "
            f"{kept[0] if kept else backup_dir()}."
        ) from exc
    try:
        _fsync_dir(DB_PATH.parent)
    except OSError:
        pass  # the restore is done; only its survival through a power cut is less certain
    return kept


# ── Init + seed ───────────────────────────────────────────────────

async def init_db() -> None:
    """Create tables, run migrations, and seed if empty."""
    async with _db() as db:
        await db.executescript(_SCHEMA)
        # Migration: add sort_order column if missing (existing DBs)
        try:
            await db.execute("ALTER TABLE projects ADD COLUMN sort_order INTEGER DEFAULT 0")
            await db.commit()
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
            await _seed_events_settings(db)
            await db.commit()


_WIPED_BY_SEED = ("logs", "notes", "sessions", "events", "settings", "viewers", "projects")


async def seed_db() -> Path | None:
    """Back up the board, then replace everything with the seed projects.
    Returns the backup's path (None when there was no board yet).

    One transaction holds the board's write lock from before the backup
    until the reset is committed, so a save from the running board can't
    land in between (it would be in neither), and a reset that fails
    partway changes nothing. Waits at most BACKUP_TIME_LIMIT for the lock.
    """
    existed = DB_PATH.exists()
    backup = None
    locked_out = True  # until the write lock is ours
    try:
        async with _db(timeout=BACKUP_TIME_LIMIT) as db:
            await db.executescript(_SCHEMA)
            await db.execute("BEGIN IMMEDIATE")
            locked_out = False
            if existed:
                backup = await asyncio.to_thread(backup_before_seed)
            for table in _WIPED_BY_SEED:
                await db.execute(f"DELETE FROM {table}")
            await _insert_seeds(db)  # commits: the whole reset lands at once
    except sqlite3.OperationalError as exc:
        if locked_out and "locked" in str(exc):
            raise BackupTimeout(f"the board stayed locked for {BACKUP_TIME_LIMIT:g}s") from exc
        raise
    return backup


# ── Projects ──────────────────────────────────────────────────────

async def list_projects() -> list[dict]:
    """Return all projects with logs attached, camelCase keys."""
    async with _db() as db:
        cursor = await db.execute("SELECT * FROM projects ORDER BY sort_order, track, name")
        rows = await cursor.fetchall()

        log_cursor = await db.execute(
            "SELECT project_id, text, created_at FROM logs ORDER BY created_at ASC"
        )
        logs_by_project: dict[str, list[dict]] = {}
        for lr in await log_cursor.fetchall():
            logs_by_project.setdefault(lr["project_id"], []).append(
                {"text": lr["text"], "at": lr["created_at"]}
            )

        projects = []
        for row in rows:
            out = PROJECTS.row_out(row)
            out["log"] = logs_by_project.get(row["id"], [])
            out["history"] = []
            projects.append(out)
        return projects


async def create_project(data: dict) -> dict:
    """Create a project from camelCase frontend data. Returns {id}."""
    now = _now()
    pid = data.get("id") or _new_id()
    async with _db() as db:
        await PROJECTS.insert(db, {
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
        })
        await db.commit()
        return {"id": pid}


async def update_project(pid: str, data: dict) -> dict:
    """Partial update from camelCase dict. Always touches updated_at and last_touched."""
    async with _db() as db:
        await PROJECTS.update(db, pid, data, touch=("updated_at", "last_touched"))
        await db.commit()
        return {"id": pid, "updated": True}


async def delete_project(pid: str) -> dict:
    """Delete project; foreign key cascade handles logs and notes."""
    async with _db() as db:
        await db.execute("DELETE FROM projects WHERE id = ?", (pid,))
        await db.commit()
        return {"id": pid, "deleted": True}


# ── Logs ──────────────────────────────────────────────────────────

async def add_log(pid: str, text: str) -> dict:
    """Insert a log entry and touch the project. Returns {text, at}."""
    now = _now()
    async with _db() as db:
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


async def get_logs(pid: str) -> list[dict]:
    """Return all logs for a project as [{text, at}]."""
    async with _db() as db:
        cursor = await db.execute(
            "SELECT text, created_at FROM logs WHERE project_id = ? ORDER BY created_at ASC",
            (pid,),
        )
        rows = await cursor.fetchall()
        return [{"text": r["text"], "at": r["created_at"]} for r in rows]


# ── Notes (flip side) ─────────────────────────────────────────────

async def get_notes(pid: str) -> dict:
    """Return {content, updatedAt} for a project, or empty defaults."""
    async with _db() as db:
        cursor = await db.execute(
            "SELECT content, updated_at FROM notes WHERE project_id = ?",
            (pid,),
        )
        row = await cursor.fetchone()
        if row:
            return {"content": row["content"], "updatedAt": row["updated_at"]}
        return {"content": "", "updatedAt": None}


async def update_notes(pid: str, content: str) -> dict:
    """Upsert notes for a project. Returns {content, updatedAt}."""
    now = _now()
    async with _db() as db:
        await db.execute(
            """INSERT INTO notes (project_id, content, updated_at)
               VALUES (?, ?, ?)
               ON CONFLICT(project_id)
               DO UPDATE SET content = excluded.content, updated_at = excluded.updated_at""",
            (pid, content, now),
        )
        await db.commit()
        return {"content": content, "updatedAt": now}


# ── Recap ─────────────────────────────────────────────────────────

async def get_recap() -> dict:
    """Today's touched projects and log count."""
    today_str = datetime.now(timezone.utc).date().isoformat()
    async with _db() as db:
        cursor = await db.execute(
            "SELECT id, name, status FROM projects WHERE last_touched LIKE ? || '%'",
            (today_str,),
        )
        touched = await cursor.fetchall()
        projects = [{"id": r["id"], "name": r["name"], "status": r["status"]} for r in touched]

        log_cursor = await db.execute(
            "SELECT COUNT(*) FROM logs WHERE created_at LIKE ? || '%'",
            (today_str,),
        )
        log_row = await log_cursor.fetchone()

        return {
            "date": today_str,
            "projectsTouched": len(projects),
            "projects": projects,
            "logEntries": log_row[0],
        }


# ── Events ────────────────────────────────────────────────────────

async def list_events() -> list[dict]:
    """Return all events, camelCase keys."""
    async with _db() as db:
        cursor = await db.execute("SELECT * FROM events ORDER BY time")
        rows = await cursor.fetchall()
        return [EVENTS.row_out(row) for row in rows]


async def create_event(data: dict) -> dict:
    """Create event. Returns {id}. Accepts: time, endTime, name, source, linkedProject."""
    now = _now()
    eid = data.get("id") or _new_id()
    async with _db() as db:
        await EVENTS.insert(db, {
            "id": eid,
            "time": data.get("time", ""),
            "end_time": data.get("endTime", ""),
            "name": data.get("name", ""),
            "source": data.get("source", ""),
            "linked_project": data.get("linkedProject", ""),
            "created_at": now,
            "updated_at": now,
        })
        await db.commit()
        return {"id": eid}


async def update_event(eid: str, data: dict) -> dict:
    """Partial update. Returns {id, updated: True}."""
    async with _db() as db:
        await EVENTS.update(db, eid, data, touch=("updated_at",))
        await db.commit()
        return {"id": eid, "updated": True}


async def delete_event(eid: str) -> dict:
    """Delete event. Returns {id, deleted: True}."""
    async with _db() as db:
        await db.execute("DELETE FROM events WHERE id = ?", (eid,))
        await db.commit()
        return {"id": eid, "deleted": True}


# ── Settings ──────────────────────────────────────────────────────

async def get_settings() -> dict:
    """Return all settings as {key: value} dict."""
    async with _db() as db:
        cursor = await db.execute("SELECT key, value FROM settings")
        rows = await cursor.fetchall()
        return {r["key"]: r["value"] for r in rows}


async def update_settings(data: dict) -> dict:
    """Update settings from partial dict. Returns full settings."""
    async with _db() as db:
        for key, value in data.items():
            await db.execute(
                "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
                (key, str(value)),
            )
        await db.commit()
        cursor = await db.execute("SELECT key, value FROM settings")
        rows = await cursor.fetchall()
        return {r["key"]: r["value"] for r in rows}


# ── Viewers ───────────────────────────────────────────────────────

async def add_viewer(email: str) -> dict:
    """Add a viewer by email. Generates a unique token. Returns {id, email, token, createdAt}."""
    async with _db() as db:
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


async def list_viewers() -> list[dict]:
    """Return all viewers as [{id, email, token, createdAt, lastSeen}]."""
    async with _db() as db:
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


async def remove_viewer(vid: str) -> dict:
    """Delete a viewer. Returns {id, deleted: True}."""
    async with _db() as db:
        await db.execute("DELETE FROM viewers WHERE id = ?", (vid,))
        await db.commit()
        return {"id": vid, "deleted": True}


async def get_viewer_by_token(token: str) -> dict | None:
    """Look up a viewer by token. Returns {id, email, token} or None."""
    async with _db() as db:
        cursor = await db.execute(
            "SELECT id, email, token FROM viewers WHERE token = ?",
            (token,),
        )
        row = await cursor.fetchone()
        if row:
            return {"id": row["id"], "email": row["email"], "token": row["token"]}
        return None


async def touch_viewer(vid: str) -> None:
    """Update last_seen timestamp for a viewer."""
    async with _db() as db:
        await db.execute(
            "UPDATE viewers SET last_seen = ? WHERE id = ?",
            (_now(), vid),
        )
        await db.commit()
