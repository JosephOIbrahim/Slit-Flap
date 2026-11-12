"""The recap is the owner's day, even when UTC has already rolled over."""

import asyncio
import sqlite3
from contextlib import closing
from datetime import datetime, timedelta, timezone

from departures import db


def put(conn, project_id, last_touched=None, log_at=None):
    conn.execute("INSERT INTO projects (id, name, last_touched) VALUES (?, ?, ?)",
                 (project_id, project_id, last_touched))
    if log_at:
        conn.execute("INSERT INTO logs (project_id, text, created_at) VALUES (?, 'x', ?)",
                     (project_id, log_at))


def test_recap_is_the_local_day_even_after_utc_midnight(board, monkeypatch):
    # 8pm on 12 November in UTC-5 is already 1am on 13 November in UTC.
    tz = timezone(timedelta(hours=-5))
    monkeypatch.setattr(db, "_local_now", lambda: datetime(2027, 1, 15, 20, 0, tzinfo=tz))
    asyncio.run(db.init_db())
    with closing(sqlite3.connect(db.DB_PATH)) as conn:
        put(conn, "evening", "2027-01-16T00:30:00+00:00", "2027-01-16T04:59:00+00:00")
        put(conn, "midnight", "2027-01-15T05:00:00+00:00")       # first instant of the day
        put(conn, "tomorrow", "2027-01-16T06:00:00+00:00")       # 1am local on the 13th
        conn.commit()

    recap = asyncio.run(db.get_recap())
    assert recap["date"] == "2027-01-15"
    assert {p["id"] for p in recap["projects"]} == {"evening", "midnight"}
    assert recap["logEntries"] == 1


def test_recap_leaves_out_the_next_local_day(board, monkeypatch):
    tz = timezone(timedelta(hours=-5))
    monkeypatch.setattr(db, "_local_now", lambda: datetime(2027, 1, 15, 20, 0, tzinfo=tz))
    asyncio.run(db.init_db())
    with closing(sqlite3.connect(db.DB_PATH)) as conn:
        put(conn, "next", "2027-01-16T06:00:00+00:00", "2027-01-16T05:00:00+00:00")  # local 1am on 13th
        conn.commit()
    recap = asyncio.run(db.get_recap())
    assert recap["projects"] == []
    assert recap["logEntries"] == 0
