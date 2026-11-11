"""Daily backups: one verified copy per day, the newest 14 kept, and a
failed backup never stops the board."""

import sqlite3
from contextlib import closing
from datetime import date, timedelta

from fastapi.testclient import TestClient

from departures import db, server

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
