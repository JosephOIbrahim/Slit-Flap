"""Daily backups: one verified copy per day the board changed, the newest
14 kept, and a failed backup never stops the board. Restoring: `departures restore` puts a
backup back without the leftover-file corruption a hand restore risks."""

import asyncio
import os
import shutil
import sqlite3
import subprocess
import sys
import threading
import time
from contextlib import closing
from datetime import date, timedelta
from pathlib import Path

import pytest
from click.testing import CliRunner
from fastapi.testclient import TestClient

from departures import cli as cli_module
from departures import db, server
from departures.cli import cli

from .conftest import OWNER


def start_board():
    """One full start → request → stop of the app, like opening the board."""
    with TestClient(server.app, client=OWNER, base_url="http://localhost:4040") as client:
        assert client.get("/api/projects").status_code == 200


def daily_backups():
    return sorted(p.name for p in db.backup_dir().glob("departures-????-??-??.db"))


def project_count(path):
    with closing(sqlite3.connect(path)) as conn:
        return conn.execute("SELECT COUNT(*) FROM projects").fetchone()[0]


def test_first_use_of_the_day_makes_a_backup(board):
    start_board()
    assert daily_backups() == [f"departures-{date.today().isoformat()}.db"]


def test_backup_is_a_verified_standalone_copy(board):
    start_board()
    backup = db.backup_dir() / daily_backups()[0]
    assert project_count(backup) == project_count(db.DB_PATH) == 16
    with closing(sqlite3.connect(backup)) as conn:
        assert conn.execute("PRAGMA journal_mode").fetchone()[0] == "delete"
        assert conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"
    assert not list(db.backup_dir().glob("*.partial"))


def test_only_one_backup_per_day(board, monkeypatch):
    start_board()
    first = db.backup_dir() / daily_backups()[0]
    stamp = first.stat().st_mtime_ns

    monkeypatch.setattr(server, "_backups", server._Backups())  # a restart, same day
    start_board()
    assert len(daily_backups()) == 1
    assert first.stat().st_mtime_ns == stamp  # the morning copy is never overwritten


def test_board_left_running_still_backs_up_each_day(owner, monkeypatch):
    owner.get("/api/projects")
    owner.post("/api/projects", json={"name": "Worked On Today"})
    tomorrow = date.today() + timedelta(days=1)
    monkeypatch.setattr(server, "_today", lambda: tomorrow)
    owner.get("/api/projects")
    assert f"departures-{tomorrow.isoformat()}.db" in daily_backups()


def test_a_day_with_no_changes_gets_no_new_copy(board):
    start_board()  # today's copy
    later = [date.today() + timedelta(days=n) for n in (1, 2, 3)]

    assert db.backup_daily(later[0]) is None  # nothing changed since today's copy

    with closing(sqlite3.connect(db.DB_PATH)) as conn:  # same rows, new page layout
        conn.execute("VACUUM")
    assert db.backup_daily(later[1]) is None

    assert back_up_on(later[2]) is not None  # a real change gets its copy
    assert daily_backups() == [f"departures-{day.isoformat()}.db" for day in (date.today(), later[2])]
    assert not list(db.backup_dir().glob("*.partial"))


def test_a_viewers_visit_does_not_count_as_a_change(board):
    # Sharing the board read-only updates "last seen" on every visit. That's
    # bookkeeping, not a change to the board, so a quiet day is still skipped.
    asyncio.run(db.init_db())
    invite = asyncio.run(db.add_viewer("friend@example.com"))
    start_board()  # today's copy includes the viewer row
    with TestClient(server.app, client=("192.168.1.77", 50000),
                    base_url="http://192.168.1.10:4040",
                    cookies={"viewer_token": invite["token"]}) as viewer:
        assert viewer.get("/api/projects").status_code == 200  # touches last_seen
    tomorrow = date.today() + timedelta(days=1)
    assert db.backup_daily(tomorrow) is None
    assert daily_backups() == [f"departures-{date.today().isoformat()}.db"]


def test_a_damaged_newest_copy_gets_a_fresh_one(board):
    # Damage only in an index doesn't change what the rows say, so the
    # fingerprint alone would call the board unchanged and skip forever.
    start_board()
    [newest] = db.backup_dir().glob("departures-????-??-??.db")
    with closing(sqlite3.connect(newest)) as conn:
        page = conn.execute("PRAGMA page_size").fetchone()[0]
        root = conn.execute("SELECT rootpage FROM sqlite_master WHERE type='index'").fetchone()[0]
    with open(newest, "r+b") as f:
        f.seek((root - 1) * page)
        f.write(bytes([0xFF]) * 16)
    with closing(sqlite3.connect(newest)) as conn:
        assert conn.execute("PRAGMA quick_check").fetchone()[0] != "ok"

    made = db.backup_daily(date.today() + timedelta(days=1))
    assert made is not None and made.exists()
    with closing(sqlite3.connect(made)) as conn:
        assert conn.execute("PRAGMA quick_check").fetchone()[0] == "ok"


def test_keeps_the_newest_14_days(board):
    start_board()  # today's backup
    days_ago = [date.today() - timedelta(days=n) for n in range(40, 20, -1)]
    for day in days_ago:  # twenty older days, oldest first, each with a change
        back_up_on(day)
    kept = daily_backups()
    assert len(kept) == db.BACKUP_DAYS
    assert kept[-1] == f"departures-{date.today().isoformat()}.db"
    assert f"departures-{days_ago[-1].isoformat()}.db" in kept
    assert f"departures-{days_ago[0].isoformat()}.db" not in kept


def back_up_on(day):
    """Something changes on the board, then that day's backup is taken."""
    with closing(sqlite3.connect(db.DB_PATH)) as conn:
        conn.execute("INSERT INTO logs (project_id, text, created_at) VALUES ('departures', ?, ?)",
                     (f"worked on {day}", day.isoformat()))
        conn.commit()
    return db.backup_daily(day)


def test_a_clock_set_back_never_deletes_the_backup_just_made(board):
    # Fourteen backups from before the PC's clock jumped back (a dead clock
    # battery can reset it to an old year). Today's copy sorts oldest by name.
    start_board()
    for n in range(1, db.BACKUP_DAYS):
        back_up_on(date.today() + timedelta(days=n))
    assert len(daily_backups()) == db.BACKUP_DAYS

    made = back_up_on(date(2020, 1, 1))
    assert made is not None and made.exists()
    assert "departures-2020-01-01.db" in daily_backups()
    assert len(daily_backups()) == db.BACKUP_DAYS


def test_an_old_backup_that_cannot_be_deleted_is_left_for_later(board, monkeypatch, caplog):
    asyncio.run(db.init_db())
    oldest = back_up_on(date.today() - timedelta(days=30))
    for n in range(29, 14, -1):  # fifteen more old days
        shutil.copyfile(oldest, db.backup_dir() / f"departures-{(date.today() - timedelta(days=n)).isoformat()}.db")

    real_unlink = Path.unlink

    def unlink(self, missing_ok=False):  # the oldest is open in another program
        if self == oldest:
            raise PermissionError(13, "The file is being used by another process", str(self))
        return real_unlink(self, missing_ok=missing_ok)

    monkeypatch.setattr(Path, "unlink", unlink)
    made = back_up_on(date.today())  # no error: the day's backup is done

    assert made is not None and made.exists()
    kept = daily_backups()
    assert oldest.name in kept
    assert len(kept) == db.BACKUP_DAYS + 1  # every other old copy was still pruned
    assert "couldn't delete old backup" in caplog.text


def test_neighbor_requests_do_not_trigger_backups(neighbor, monkeypatch):
    neighbor.get("/api/projects")  # turned away at the door
    monkeypatch.setattr(server, "_today", lambda: date.today() + timedelta(days=1))
    neighbor.get("/api/projects")
    assert daily_backups() == []


def test_made_up_invite_links_do_not_trigger_backups(neighbor):
    # /join/... passes auth before anyone is known; it must not run the backup
    neighbor.get("/join/AAAA")
    neighbor.post("/join/AAAA")
    neighbor.options("/join/AAAA")
    neighbor.head("/join/AAAA")
    assert daily_backups() == []


def test_an_invited_viewer_still_triggers_the_days_backup(owner, make_viewer, monkeypatch):
    viewer, _ = make_viewer()  # the owner's invite request took today's backup
    owner.post("/api/projects", json={"name": "Changed Since"})
    tomorrow = date.today() + timedelta(days=1)
    monkeypatch.setattr(server, "_today", lambda: tomorrow)
    viewer.get("/api/projects")
    assert f"departures-{tomorrow.isoformat()}.db" in daily_backups()


def test_a_failed_backup_never_stops_the_board(board, monkeypatch, caplog):
    def broken(today):
        raise OSError("disk full")

    monkeypatch.setattr(db, "backup_daily", broken)
    start_board()  # first start creates the board
    monkeypatch.setattr(server, "_backups", server._Backups())
    start_board()  # second start: backup fails, board still answers
    assert "daily backup failed" in caplog.text


def test_a_failed_backup_is_tried_again_half_an_hour_later(owner, monkeypatch):
    owner.get("/api/projects")  # today's backup
    owner.post("/api/projects", json={"name": "Worked On Today"})
    tomorrow = date.today() + timedelta(days=1)
    monkeypatch.setattr(server, "_today", lambda: tomorrow)
    now = [1000.0]
    monkeypatch.setattr(server, "_clock", lambda: now[0])

    real_backup, attempts = db.backup_daily, []

    def disk_full_the_first_time(day):
        attempts.append(day)
        if len(attempts) == 1:
            raise OSError(28, "No space left on device")
        return real_backup(day)

    monkeypatch.setattr(db, "backup_daily", disk_full_the_first_time)
    owner.get("/api/projects")  # the day's backup fails
    now[0] += server.BACKUP_RETRY_SECONDS - 1
    owner.get("/api/projects")  # too soon to try again
    assert len(attempts) == 1

    now[0] += 1
    owner.get("/api/projects")  # tried again, and this time it works
    assert len(attempts) == 2
    assert f"departures-{tomorrow.isoformat()}.db" in daily_backups()
    owner.get("/api/projects")  # and then it's done for the day
    assert len(attempts) == 2


# ── The owner can see when backups are failing ──────────────────
# Under the silent launcher there's no terminal to read, so the board's
# header shows it (it polls /api/session every minute).

def test_the_board_shows_when_backups_are_failing(owner, monkeypatch):
    session = owner.get("/api/session").json()  # today's backup works
    assert session["backupFailed"] is False
    assert session["lastBackup"] == date.today().isoformat()

    owner.post("/api/projects", json={"name": "Worked On Today"})
    tomorrow = date.today() + timedelta(days=1)
    monkeypatch.setattr(server, "_today", lambda: tomorrow)
    now = [1000.0]
    monkeypatch.setattr(server, "_clock", lambda: now[0])
    real_backup = db.backup_daily

    def disk_full(day):
        raise OSError(28, "No space left on device", str(db.backup_dir()))

    monkeypatch.setattr(db, "backup_daily", disk_full)
    session = owner.get("/api/session").json()
    assert session["backupFailed"] is True
    assert session["lastBackup"] == date.today().isoformat()  # still the newest good one
    assert "No space" not in str(session)  # the reason stays in the log

    monkeypatch.setattr(db, "backup_daily", real_backup)  # space freed up
    now[0] += server.BACKUP_RETRY_SECONDS
    session = owner.get("/api/session").json()
    assert session["backupFailed"] is False
    assert session["lastBackup"] == tomorrow.isoformat()


def test_viewers_are_not_told_about_backups(make_viewer):
    viewer, _ = make_viewer()
    session = viewer.get("/api/session").json()
    assert "startedAt" in session
    assert "backupFailed" not in session and "lastBackup" not in session


def damage_the_board():
    """Scribble over the projects table, as a failing disk or a crash in the
    middle of a write could."""
    with closing(sqlite3.connect(db.DB_PATH)) as conn:
        page_size = conn.execute("PRAGMA page_size").fetchone()[0]
        root = conn.execute("SELECT rootpage FROM sqlite_master WHERE name = 'projects'").fetchone()[0]
    with open(db.DB_PATH, "r+b") as board_file:
        board_file.seek((root - 1) * page_size)
        board_file.write(b"\xff" * 16)


def test_a_damaged_board_is_reported_as_damaged(owner, monkeypatch, caplog):
    owner.get("/api/session")  # today's good backup
    damage_the_board()
    tomorrow = date.today() + timedelta(days=1)
    monkeypatch.setattr(server, "_today", lambda: tomorrow)

    with pytest.raises(db.BackupCheckFailed):
        db.backup_daily(tomorrow)

    session = owner.get("/api/session").json()  # /api/session doesn't read the board
    assert session["backupFailed"] is True
    assert session["lastBackup"] == date.today().isoformat()
    assert f"departures-{tomorrow.isoformat()}.db" not in daily_backups()
    assert not list(db.backup_dir().glob("*.partial"))
    [warning] = [r for r in caplog.records if "may be damaged" in r.getMessage()]
    assert warning.levelname == "ERROR"
    assert daily_backups()[-1] in warning.getMessage()  # names the copy to go back to


# ── A locked board can't hold anything up ───────────────────────
# Python's SQLite backup waits forever while another program holds the
# board locked. Backups give up after db.BACKUP_TIME_LIMIT (shortened here).

def lock_the_board():
    """Another program holding the board in an exclusive lock (say, a
    database tool in the middle of a write): no one else can even read it."""
    holder = sqlite3.connect(db.DB_PATH)
    holder.execute("PRAGMA locking_mode=EXCLUSIVE")
    holder.execute("BEGIN EXCLUSIVE")
    return holder


def finishes_within(seconds, work):
    """Run work() on a helper thread; report whether it finished in time.

    A test that would otherwise hang (if the time limit ever broke) fails
    instead: the caller releases the lock right after, so nothing stays stuck.
    """
    outcome = {}

    def run():
        try:
            outcome["result"] = work()
        except BaseException as exc:
            outcome["error"] = exc

    helper = threading.Thread(target=run, daemon=True)
    helper.start()
    helper.join(seconds)
    return not helper.is_alive(), outcome, helper


def test_a_locked_board_cannot_hang_a_backup(board, monkeypatch):
    start_board()
    monkeypatch.setattr(db, "BACKUP_TIME_LIMIT", 0.5)
    tomorrow = date.today() + timedelta(days=1)

    holder = lock_the_board()
    try:
        finished, outcome, helper = finishes_within(5, lambda: db.backup_daily(tomorrow))
    finally:
        holder.close()
    helper.join(30)

    assert finished, "the backup was still waiting on the locked board after 5s"
    assert isinstance(outcome.get("error"), db.BackupTimeout)
    assert f"departures-{tomorrow.isoformat()}.db" not in daily_backups()
    assert not list(db.backup_dir().glob("*.partial"))


def test_a_locked_board_cannot_hang_the_first_request_of_the_day(owner, monkeypatch, caplog):
    owner.get("/api/projects")  # today's backup is done
    monkeypatch.setattr(db, "BACKUP_TIME_LIMIT", 0.5)
    monkeypatch.setattr(server, "_today", lambda: date.today() + timedelta(days=1))

    holder = lock_the_board()
    try:
        # /api/session doesn't read the board: only the backup could hold it up
        finished, outcome, helper = finishes_within(5, lambda: owner.get("/api/session"))
    finally:
        holder.close()
    helper.join(30)

    assert finished, "the first request of the day waited on the locked board"
    assert outcome["result"].status_code == 200
    assert "stayed locked" in caplog.text


def test_startup_with_a_locked_board_skips_the_backup_and_carries_on(board, monkeypatch, caplog):
    start_board()  # a board exists
    monkeypatch.setattr(server, "_backups", server._Backups())  # a restart...
    monkeypatch.setattr(server, "_today", lambda: date.today() + timedelta(days=1))  # ...on a new day
    monkeypatch.setattr(db, "BACKUP_TIME_LIMIT", 0.5)

    locked = threading.Event()

    def hold_for_two_seconds():  # e.g. a database tool finishing a write
        holder = lock_the_board()
        locked.set()
        time.sleep(2)
        holder.close()

    other_program = threading.Thread(target=hold_for_two_seconds)
    other_program.start()
    locked.wait(5)
    finished, outcome, helper = finishes_within(15, start_board)
    other_program.join(10)
    helper.join(30)

    assert finished and "error" not in outcome, outcome.get("error")
    assert "stayed locked" in caplog.text  # skipped with a warning, then the board came up


def test_seed_on_a_locked_board_explains_and_changes_nothing(board, monkeypatch):
    start_board()
    before = ids_in(db.DB_PATH)
    monkeypatch.setattr(db, "BACKUP_TIME_LIMIT", 0.5)

    holder = lock_the_board()
    try:
        finished, outcome, helper = finishes_within(
            5, lambda: CliRunner().invoke(cli, ["seed", "--yes"]))
    finally:
        holder.close()
    helper.join(30)

    assert finished, "seed was still waiting on the locked board after 5s"
    result = outcome["result"]
    assert result.exit_code != 0
    assert "Nothing was changed" in result.output
    assert ids_in(db.DB_PATH) == before


# ── Restoring a backup ──────────────────────────────────────────

@pytest.fixture
def restore(board, monkeypatch):
    """Run `departures restore ...` against the test board. The "is the
    board running?" check is stubbed so tests never knock on a real port."""
    monkeypatch.setattr(cli_module, "_board_already_running", lambda port: False)

    def run(*args, input=None):
        return CliRunner().invoke(cli, ["restore", *map(str, args)], input=input)

    return run


def ids_in(path):
    """Project ids in a board file (SQLite applies any -wal beside it)."""
    with closing(sqlite3.connect(path)) as conn:
        return {row[0] for row in conn.execute("SELECT id FROM projects")}


def crash_while_writing(sql):
    """Another Python writes to the board and dies without closing it, like
    a crash or a killed server. Its changes stay in departures.db-wal."""
    code = (
        "import os, sqlite3, sys\n"
        "conn = sqlite3.connect(sys.argv[1])\n"
        "conn.execute('PRAGMA journal_mode=WAL')\n"
        "conn.executescript(sys.argv[2])\n"
        "os._exit(0)\n"
    )
    subprocess.run([sys.executable, "-c", code, str(db.DB_PATH), sql], check=True)


def no_restore_leftovers():
    return (not list(db.backup_dir().glob("*-before-restore*"))
            and not list(db.DB_DIR.glob("*.restoring*")))


def test_restore_puts_a_backup_back_cleanly_even_after_a_crash(restore):
    start_board()  # the board, plus today's backup
    backup = db.backup_dir() / daily_backups()[0]
    crash_while_writing("DELETE FROM projects WHERE id = 'brand-refresh';"
                        "INSERT INTO projects (id, name) VALUES ('after-backup', 'After Backup');")
    wal = db.DB_PATH.with_name("departures.db-wal")
    assert wal.stat().st_size > 0  # the leftover that corrupts a hand restore

    result = restore(backup, "--yes")
    assert result.exit_code == 0, result.output

    assert not wal.exists()
    with closing(sqlite3.connect(db.DB_PATH)) as conn:
        assert conn.execute("PRAGMA integrity_check").fetchone()[0] == "ok"
    assert ids_in(db.DB_PATH) == ids_in(backup)  # exactly what the backup held
    start_board()  # and the board runs on it

    # The board from before the restore, crash changes and all, is kept as
    # one self-contained file (its -wal folded in, nothing to carry along)
    [kept] = db.backup_dir().glob("*-before-restore.db")
    assert not list(db.backup_dir().glob("*-before-restore.db-*"))  # (checked before opening it)
    assert "after-backup" in ids_in(kept)


def test_leftovers_of_a_missing_board_are_never_replayed_onto_the_restore(restore, tmp_path):
    start_board()
    backup = db.backup_dir() / daily_backups()[0]
    crash_while_writing("DELETE FROM projects WHERE id = 'brand-refresh';"
                        "INSERT INTO projects (id, name) VALUES ('stale', 'Stale');")
    db.DB_PATH.rename(tmp_path / "moved-away.db")  # moved by hand; its -wal stayed behind
    wal = db.DB_PATH.with_name("departures.db-wal")
    assert wal.exists()

    result = restore(backup, "--yes")
    assert result.exit_code == 0, result.output
    assert not wal.exists()
    assert ids_in(db.DB_PATH) == ids_in(backup)
    assert "Leftover files of a missing board kept at" in result.output
    start_board()  # the board starts on exactly the backup, nothing replayed
    assert ids_in(db.DB_PATH) == ids_in(backup)


def test_restore_keeps_the_wal_of_a_zero_byte_board(restore, tmp_path):
    # A crash can leave departures.db empty with the real changes still in
    # its -wal. The copy kept must include that -wal, not an empty board.
    start_board()
    backup = db.backup_dir() / daily_backups()[0]
    crash_while_writing("INSERT INTO projects (id, name) VALUES ('wonly', 'WAL Only');")
    wal = db.DB_PATH.with_name("departures.db-wal")
    assert wal.stat().st_size > 0
    original_wal = wal.read_bytes()
    open(db.DB_PATH, "wb").close()  # the main file cut to nothing

    result = restore(backup, "--yes")
    assert result.exit_code == 0, result.output
    [kept_wal] = db.backup_dir().glob("*-before-restore.db-wal")
    assert kept_wal.read_bytes() == original_wal  # the changes are kept, not deleted


def test_a_restore_that_fails_at_the_swap_leaves_the_board_as_it_was(restore, monkeypatch):
    start_board()
    backup = db.backup_dir() / daily_backups()[0]
    asyncio.run(db.create_project({"id": "newer", "name": "Newer"}))
    before = ids_in(db.DB_PATH)
    real_replace = os.replace

    def replace(src, dst, *args, **kwargs):  # the final rename onto the board fails
        if Path(dst) == db.DB_PATH:
            raise PermissionError(13, "Access is denied", str(dst))
        return real_replace(src, dst, *args, **kwargs)

    monkeypatch.setattr(os, "replace", replace)
    result = restore(backup, "--yes")
    assert result.exit_code != 0
    assert "Nothing was changed" in result.output
    assert ids_in(db.DB_PATH) == before
    assert no_restore_leftovers()
    start_board()  # the owner's board, not a fresh demo board
    assert ids_in(db.DB_PATH) == before


def test_a_damaged_board_can_be_restored_over_and_is_kept_as_it_was(restore):
    start_board()
    backup = db.backup_dir() / daily_backups()[0]
    damage_the_board()
    damaged = db.DB_PATH.read_bytes()

    result = restore(backup, "--yes")
    assert result.exit_code == 0, result.output
    assert ids_in(db.DB_PATH) == ids_in(backup)
    [kept] = db.backup_dir().glob("*-before-restore.db")
    assert kept.read_bytes() == damaged  # too damaged to copy cleanly: kept byte for byte


def test_restore_asks_first_and_no_changes_nothing(restore):
    start_board()
    backup = db.backup_dir() / daily_backups()[0]
    asyncio.run(db.create_project({"id": "newer", "name": "Newer"}))

    result = restore(backup, input="n\n")
    assert result.exit_code != 0
    assert "now:" in result.output and "backup:" in result.output
    assert "newer" in ids_in(db.DB_PATH)
    assert no_restore_leftovers()


def test_restore_refuses_a_file_that_is_not_a_board(restore, tmp_path):
    start_board()
    before = ids_in(db.DB_PATH)
    junk = tmp_path / "not-a-board.db"
    junk.write_text("just some text", encoding="utf-8")

    result = restore(junk, "--yes")
    assert result.exit_code != 0
    assert "isn't a readable board" in result.output
    assert ids_in(db.DB_PATH) == before
    assert no_restore_leftovers()


def test_restore_refuses_another_apps_database(restore, tmp_path):
    start_board()
    before = ids_in(db.DB_PATH)
    other_app = tmp_path / "other-app.db"
    with closing(sqlite3.connect(other_app)) as conn:  # healthy, and it even has "projects"
        conn.execute("CREATE TABLE projects (id INTEGER PRIMARY KEY, title TEXT)")
        conn.execute("INSERT INTO projects (title) VALUES ('Not Ours')")
        conn.commit()

    result = restore(other_app, "--yes")
    assert result.exit_code != 0
    assert "isn't a DEPARTURES board" in result.output and "projects" in result.output
    assert ids_in(db.DB_PATH) == before
    assert no_restore_leftovers()


def test_restore_takes_a_board_from_before_sort_order(restore, tmp_path):
    start_board()
    older = tmp_path / "from-an-older-version.db"
    shutil.copyfile(db.backup_dir() / daily_backups()[0], older)
    with closing(sqlite3.connect(older)) as conn:
        conn.execute("ALTER TABLE projects DROP COLUMN sort_order")
        conn.commit()

    result = restore(older, "--yes")
    assert result.exit_code == 0, result.output
    start_board()  # the board adds the column back and runs on it


def test_restore_checks_the_port_the_board_was_started_on(restore, monkeypatch):
    start_board()
    backup = db.backup_dir() / daily_backups()[0]
    asked = []
    monkeypatch.setattr(cli_module, "_board_already_running", lambda port: asked.append(port) or True)

    result = CliRunner().invoke(cli, ["--port", "9123", "restore", str(backup), "--yes"])
    assert result.exit_code != 0
    assert asked == [9123]
    assert "running on port 9123" in result.output


def test_restore_checks_again_after_asking(restore, monkeypatch):
    start_board()
    backup = db.backup_dir() / daily_backups()[0]
    before = ids_in(db.DB_PATH)
    running = iter([False, True])  # stopped when asked; started while the question waited
    monkeypatch.setattr(cli_module, "_board_already_running", lambda port: next(running))

    result = restore(backup, input="y\n")
    assert result.exit_code != 0
    assert "running" in result.output
    assert ids_in(db.DB_PATH) == before
    assert no_restore_leftovers()


def test_restore_warns_when_removed_viewer_links_would_work_again(restore):
    asyncio.run(db.init_db())
    removed = asyncio.run(db.add_viewer("removed@example.com"))
    asyncio.run(db.add_viewer("still-invited@example.com"))
    backup = db.backup_daily(date.today())
    asyncio.run(db.remove_viewer(removed["id"]))  # the owner revokes a link

    asked = restore(backup, input="n\n")
    assert "removed@example.com" in asked.output and "brings them back" in asked.output
    assert "still-invited@example.com" not in asked.output  # that one never went away

    done = restore(backup, "--yes")
    assert done.exit_code == 0, done.output
    assert "came back with the backup" in done.output and "removed@example.com" in done.output


def test_restore_refuses_while_the_board_is_running(restore, monkeypatch):
    start_board()
    backup = db.backup_dir() / daily_backups()[0]
    monkeypatch.setattr(cli_module, "_board_already_running", lambda port: True)

    result = restore(backup, "--yes")
    assert result.exit_code != 0
    assert "running" in result.output
    assert no_restore_leftovers()


@pytest.mark.skipif(sys.platform != "win32", reason="Windows locks open database files")
def test_restore_changes_nothing_while_the_board_is_open_elsewhere(restore):
    start_board()
    backup = db.backup_dir() / daily_backups()[0]
    before = ids_in(db.DB_PATH)

    with closing(sqlite3.connect(db.DB_PATH)) as other_program:
        other_program.execute("SELECT COUNT(*) FROM projects").fetchone()
        result = restore(backup, "--yes")

    assert result.exit_code != 0
    assert "Nothing was changed" in result.output
    assert ids_in(db.DB_PATH) == before
    assert no_restore_leftovers()


def test_restore_lists_backups_and_takes_a_bare_name(restore):
    start_board()
    name = daily_backups()[0]

    listing = restore()
    assert listing.exit_code == 0
    assert name in listing.output

    result = restore(name, "--yes")  # the name alone, found in the backups folder
    assert result.exit_code == 0, result.output
    assert "Previous board kept at" in result.output


def test_restore_onto_a_machine_with_no_board(restore, tmp_path):
    start_board()
    carried = tmp_path / "from-another-pc.db"
    shutil.copyfile(db.backup_dir() / daily_backups()[0], carried)
    for leftover in (db.DB_PATH, *db._sidecars(db.DB_PATH)):  # a fresh machine
        leftover.unlink(missing_ok=True)

    result = restore(carried, "--yes")
    assert result.exit_code == 0, result.output
    assert ids_in(db.DB_PATH) == ids_in(carried)
    assert "Previous board kept" not in result.output


# ── Counting what's on a board (shown before seed and restore) ──

def through_network_share(path):
    r"""The same file reached through this PC's own network share:
    C:\Users\...\departures.db  ->  \\localhost\C$\Users\...\departures.db"""
    full = str(Path(path).resolve())
    return Path("\\\\localhost\\" + full[0] + "$" + full[2:])


def test_counts_work_for_a_board_on_a_network_share(restore):
    start_board()
    on_share = through_network_share(db.DB_PATH)
    if sys.platform != "win32" or not on_share.exists():
        pytest.skip("needs Windows with this PC's admin share (localhost C$) reachable")

    assert db.board_counts(on_share) == db.board_counts(db.DB_PATH)

    # The restore prompt for a board kept on a share shows its counts too
    backup = db.backup_dir() / daily_backups()[0]
    on_share_home = on_share.parent
    with pytest.MonkeyPatch.context() as mp:
        mp.setattr(db, "DB_DIR", on_share_home)
        mp.setattr(db, "DB_PATH", on_share)
        result = restore(through_network_share(backup), input="n\n")
    assert "now:    projects: 16" in result.output
    assert result.exception is None or isinstance(result.exception, SystemExit)


def test_counts_fall_back_without_touching_the_board(board, monkeypatch):
    start_board()
    crash_while_writing("INSERT INTO projects (id, name) VALUES ('wal-only', 'In The WAL Only');")
    wal = db.DB_PATH.with_name("departures.db-wal")
    files_before = (db.DB_PATH.read_bytes(), wal.read_bytes())

    real_connect = sqlite3.connect

    def rejects_file_uris(target, *args, **kwargs):
        if kwargs.get("uri"):  # what a \\server\share data folder gets
            raise sqlite3.OperationalError("invalid uri authority: server")
        return real_connect(target, *args, **kwargs)

    monkeypatch.setattr(sqlite3, "connect", rejects_file_uris)
    counts = db.board_counts()

    assert counts["projects"] == 16  # the main file's count; the -wal is left alone
    assert (db.DB_PATH.read_bytes(), wal.read_bytes()) == files_before  # board untouched
