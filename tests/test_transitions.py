"""Status changes are recorded server-side, so the count survives a reload."""

import asyncio
import sqlite3
from contextlib import closing

from departures import db


def history_of(pid, archived=False):
    [project] = [p for p in asyncio.run(db.list_projects(archived=archived)) if p["id"] == pid]
    return project["history"]


def test_a_status_change_is_recorded_and_returned(board):
    asyncio.run(db.init_db())
    asyncio.run(db.create_project({"id": "p", "name": "P"}))  # QUEUED
    assert asyncio.run(db.update_project("p", {"status": "ACTIVE"}))["updated"] is True

    history = history_of("p")
    assert len(history) == 1
    assert history[0]["from"] == "QUEUED" and history[0]["to"] == "ACTIVE"
    assert history[0]["at"]


def test_other_edits_and_unchanged_status_do_not_add_transitions(board):
    asyncio.run(db.init_db())
    asyncio.run(db.create_project({"id": "p", "name": "P"}))
    asyncio.run(db.update_project("p", {"name": "Renamed"}))
    asyncio.run(db.update_project("p", {"status": "QUEUED"}))  # same status
    assert history_of("p") == []


def test_transitions_are_kept_in_order_across_reloads(board):
    asyncio.run(db.init_db())
    asyncio.run(db.create_project({"id": "p", "name": "P"}))
    for status in ("ACTIVE", "ROLLING", "REVIEW", "SHIPPED"):
        asyncio.run(db.update_project("p", {"status": status}))

    history = history_of("p")
    assert [h["to"] for h in history] == ["ACTIVE", "ROLLING", "REVIEW", "SHIPPED"]
    assert [h["from"] for h in history] == ["QUEUED", "ACTIVE", "ROLLING", "REVIEW"]


def test_archiving_keeps_history(board):
    asyncio.run(db.init_db())
    asyncio.run(db.create_project({"id": "p", "name": "P"}))
    asyncio.run(db.update_project("p", {"status": "ACTIVE"}))
    asyncio.run(db.archive_project("p"))
    assert [h["to"] for h in history_of("p", archived=True)] == ["ACTIVE"]
    asyncio.run(db.restore_project("p"))
    assert [h["to"] for h in history_of("p")] == ["ACTIVE"]


def test_the_migration_creates_transitions(board):
    asyncio.run(db.init_db())
    assert db.SCHEMA_VERSION >= 5
    with closing(sqlite3.connect(db.DB_PATH)) as conn:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert "transitions" in tables
    assert version == db.SCHEMA_VERSION
