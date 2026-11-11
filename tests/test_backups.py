"""Daily backups: one verified copy per day, the newest 14 kept, and a
failed backup never stops the board. Restoring: `departures restore` puts a
backup back without the leftover-file corruption a hand restore risks."""

import asyncio
import shutil
import sqlite3
import subprocess
import sys
from contextlib import closing
from datetime import date, timedelta

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

    monkeypatch.setattr(server, "_backup_day", None)  # a restart, same day
    start_board()
    assert len(daily_backups()) == 1
    assert first.stat().st_mtime_ns == stamp  # the morning copy is never overwritten


def test_board_left_running_still_backs_up_each_day(owner, monkeypatch):
    owner.get("/api/projects")
    tomorrow = date.today() + timedelta(days=1)
    monkeypatch.setattr(server, "_today", lambda: tomorrow)
    owner.get("/api/projects")
    assert f"departures-{tomorrow.isoformat()}.db" in daily_backups()


def test_keeps_the_newest_14_days(board):
    start_board()  # today's backup
    days_ago = [date.today() - timedelta(days=n) for n in range(40, 20, -1)]
    for day in days_ago:  # twenty older days, oldest first
        db.backup_daily(day)
    kept = daily_backups()
    assert len(kept) == db.BACKUP_DAYS
    assert kept[-1] == f"departures-{date.today().isoformat()}.db"
    assert f"departures-{days_ago[-1].isoformat()}.db" in kept
    assert f"departures-{days_ago[0].isoformat()}.db" not in kept


def test_neighbor_requests_do_not_trigger_backups(neighbor, monkeypatch):
    neighbor.get("/api/projects")  # turned away at the door
    monkeypatch.setattr(server, "_today", lambda: date.today() + timedelta(days=1))
    neighbor.get("/api/projects")
    assert daily_backups() == []


def test_a_failed_backup_never_stops_the_board(board, monkeypatch, caplog):
    def broken(today):
        raise OSError("disk full")

    monkeypatch.setattr(db, "backup_daily", broken)
    start_board()  # first start creates the board
    monkeypatch.setattr(server, "_backup_day", None)
    start_board()  # second start: backup fails, board still answers
    assert "daily backup failed" in caplog.text


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

    # The board from before the restore, crash changes and all, is kept
    [kept] = db.backup_dir().glob("*-before-restore.db")
    assert "after-backup" in ids_in(kept)


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
