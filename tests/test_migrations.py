"""Schema migrations: recorded in PRAGMA user_version, run once, in order,
and a failed step changes nothing."""

import asyncio
import sqlite3
from contextlib import closing

import pytest

from departures import db


def version(path=None):
    with closing(sqlite3.connect(path or db.DB_PATH)) as conn:
        return conn.execute("PRAGMA user_version").fetchone()[0]


def sort_orders(path=None):
    with closing(sqlite3.connect(path or db.DB_PATH)) as conn:
        return [row[0] for row in conn.execute("SELECT sort_order FROM projects ORDER BY sort_order")]


def test_a_fresh_board_records_the_latest_version(board):
    asyncio.run(db.init_db())
    assert version() == db.SCHEMA_VERSION
    orders = sort_orders()
    assert len(orders) == 16 and orders == list(range(16))  # unique, in board order


def test_a_legacy_board_gains_sort_order(board):
    # A board from before sort_order existed, and from before user_version
    # was used to track the schema.
    db.DB_DIR.mkdir(parents=True, exist_ok=True)
    with closing(sqlite3.connect(db.DB_PATH)) as conn:
        conn.execute("CREATE TABLE projects (id TEXT PRIMARY KEY, name TEXT NOT NULL, track TEXT, today_time TEXT DEFAULT '')")
        conn.executemany("INSERT INTO projects (id, name, track, today_time) VALUES (?, ?, ?, ?)",
                         [("b", "B", "02", ""), ("a", "A", "01", ""), ("c", "C", "01", "")])
        conn.commit()
    assert version() == 0

    asyncio.run(db.init_db())
    assert version() == db.SCHEMA_VERSION
    with closing(sqlite3.connect(db.DB_PATH)) as conn:
        rows = conn.execute("SELECT id, sort_order FROM projects ORDER BY sort_order").fetchall()
    assert rows == [("a", 0), ("c", 1), ("b", 2)]  # track, then name


def test_duplicate_sort_orders_are_repaired_once(board):
    asyncio.run(db.init_db())
    with closing(sqlite3.connect(db.DB_PATH)) as conn:  # a board that drifted before the migration
        conn.execute("UPDATE projects SET sort_order = 0")
        conn.execute("PRAGMA user_version = 0")
        conn.commit()

    asyncio.run(db.init_db())
    assert sort_orders() == list(range(16))


def test_a_migration_does_not_run_twice(board, monkeypatch):
    asyncio.run(db.init_db())

    async def boom(conn):
        raise AssertionError("migration 1 ran again")
    monkeypatch.setattr(db, "_MIGRATIONS", [(1, "boom", boom)])
    asyncio.run(db.init_db())  # version is already 1: nothing runs


def test_a_failed_migration_changes_nothing(board, monkeypatch):
    async def half_done(conn):
        await conn.execute("ALTER TABLE projects ADD COLUMN half_added TEXT")
        raise RuntimeError("interrupted")

    monkeypatch.setattr(db, "_MIGRATIONS", [(1, "half", half_done)])
    with pytest.raises(RuntimeError):
        asyncio.run(db.init_db())

    assert version() == 0
    with closing(sqlite3.connect(db.DB_PATH)) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(projects)")}
    assert "half_added" not in cols


def test_a_block_from_before_the_date_column_keeps_its_day(board):
    # A board at schema 1 has time blocks but no date for them. They are kept
    # visible by dating them today, not dropped from TODAY.
    from datetime import date

    asyncio.run(db.init_db())
    with closing(sqlite3.connect(db.DB_PATH)) as conn:
        conn.execute("ALTER TABLE projects DROP COLUMN today_date")
        conn.execute("UPDATE projects SET today_time = '10:00' WHERE id = 'brand-refresh'")
        conn.execute("PRAGMA user_version = 1")
        conn.commit()
    assert version() == 1

    asyncio.run(db.init_db())
    assert version() == db.SCHEMA_VERSION
    with closing(sqlite3.connect(db.DB_PATH)) as conn:
        got = conn.execute("SELECT today_date FROM projects WHERE id = 'brand-refresh'").fetchone()[0]
    assert got == date.today().isoformat()


def test_events_are_dated_and_old_ones_keep_their_day(board):
    from datetime import date

    asyncio.run(db.init_db())
    with closing(sqlite3.connect(db.DB_PATH)) as conn:
        dates = [row[0] for row in conn.execute("SELECT date FROM events")]
    assert dates and all(d == date.today().isoformat() for d in dates)

    # A board at schema 2 has events but no date for them.
    with closing(sqlite3.connect(db.DB_PATH)) as conn:
        conn.execute("ALTER TABLE events DROP COLUMN date")
        conn.execute("PRAGMA user_version = 2")
        conn.commit()
    asyncio.run(db.init_db())
    with closing(sqlite3.connect(db.DB_PATH)) as conn:
        dates = [row[0] for row in conn.execute("SELECT date FROM events")]
    assert dates and all(d == date.today().isoformat() for d in dates)


def test_deleted_demo_events_stay_deleted(board):
    asyncio.run(db.init_db())
    with closing(sqlite3.connect(db.DB_PATH)) as conn:
        conn.execute("DELETE FROM events WHERE id = 'ev1'")
        conn.commit()
    asyncio.run(db.init_db())  # the next start must not re-add it
    with closing(sqlite3.connect(db.DB_PATH)) as conn:
        ids = {row[0] for row in conn.execute("SELECT id FROM events")}
    assert "ev1" not in ids


def test_demo_mode_is_true_only_for_the_seed_board(board):
    asyncio.run(db.init_db())
    assert asyncio.run(db.get_settings())["demo"] is True
    asyncio.run(db.create_project({"id": "real", "name": "Real"}))
    assert asyncio.run(db.get_settings())["demo"] is False


def test_an_old_sessions_table_gains_the_columns_the_pulse_writes(board):
    asyncio.run(db.init_db())
    with closing(sqlite3.connect(db.DB_PATH)) as conn:
        conn.execute("ALTER TABLE sessions DROP COLUMN summary")
        conn.execute("PRAGMA user_version = 5")
        conn.commit()
    asyncio.run(db.init_db())
    with closing(sqlite3.connect(db.DB_PATH)) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(sessions)")}
        version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert "summary" in cols
    assert version == db.SCHEMA_VERSION
    sid = asyncio.run(db.start_session("2026-11-12T10:00:00+00:00"))  # the pulse's insert
    assert sid
