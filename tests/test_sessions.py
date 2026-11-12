"""The pulse measures a stretch of work, not how long the server has been up."""

import asyncio
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone

from departures import db, server


def sessions():
    with closing(sqlite3.connect(db.DB_PATH)) as conn:
        return conn.execute(
            "SELECT started_at, ended_at FROM sessions ORDER BY id").fetchall()


def test_the_pulse_starts_with_activity_and_restarts_after_a_gap(board, owner, monkeypatch):
    t0 = datetime(2026, 11, 12, 9, 0, tzinfo=timezone.utc)
    now = [t0]
    monkeypatch.setattr(server, "_now", lambda: now[0])

    # Polling alone is not work.
    first = owner.get("/api/session").json()
    assert first["sessionStartedAt"] is None
    assert first["elapsedMinutes"] == 0
    assert sessions() == []

    owner.get("/api/projects")  # the first real interaction starts a session
    started = owner.get("/api/session").json()
    assert started["sessionStartedAt"] == t0.isoformat()
    assert started["elapsedMinutes"] == 0
    assert len(sessions()) == 1

    now[0] = t0 + timedelta(minutes=10)
    assert owner.get("/api/session").json()["elapsedMinutes"] == 10

    now[0] = t0 + timedelta(minutes=56)  # 46 minutes since the last request
    owner.get("/api/projects")
    rows = sessions()
    assert len(rows) == 2
    assert rows[0][1] is not None  # the first session was closed at the new start
    assert owner.get("/api/session").json()["elapsedMinutes"] == 0


def test_viewer_activity_does_not_start_the_owners_session(owner, make_viewer):
    viewer, _ = make_viewer()  # inviting is owner activity: one session
    before = len(sessions())
    viewer.get("/api/projects")
    assert len(sessions()) == before


def test_a_crash_left_session_is_closed_at_boot(board):
    asyncio.run(db.init_db())
    sid = asyncio.run(db.start_session("2026-11-12T09:00:00+00:00"))
    asyncio.run(db.close_open_sessions("2026-11-12T10:00:00+00:00"))
    with closing(sqlite3.connect(db.DB_PATH)) as conn:
        ended = conn.execute("SELECT ended_at FROM sessions WHERE id = ?", (sid,)).fetchone()[0]
    assert ended == "2026-11-12T10:00:00+00:00"
