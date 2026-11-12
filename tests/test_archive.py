"""Archive hides a project; nothing is deleted, and restore brings it back."""

import asyncio
import sqlite3
from contextlib import closing

from departures import db


def ids(listing):
    return {p["id"] for p in listing}


def test_archiving_hides_but_keeps_everything(board):
    asyncio.run(db.init_db())
    asyncio.run(db.create_project({"id": "keepme", "name": "Keep Me"}))
    asyncio.run(db.add_log("keepme", "a thought"))
    asyncio.run(db.update_notes("keepme", "a note"))

    assert asyncio.run(db.archive_project("keepme")) == {"id": "keepme", "archived": True}
    assert "keepme" not in ids(asyncio.run(db.list_projects()))
    assert "keepme" in ids(asyncio.run(db.list_projects(archived=True)))

    # Notes and logs are still there, and restore returns the card to the board.
    assert asyncio.run(db.get_notes("keepme"))["content"] == "a note"
    assert [l["text"] for l in asyncio.run(db.get_logs("keepme"))] == ["a thought"]
    assert asyncio.run(db.restore_project("keepme")) == {"id": "keepme", "archived": False}
    assert "keepme" in ids(asyncio.run(db.list_projects()))


def test_archiving_a_missing_project_is_none(board):
    asyncio.run(db.init_db())
    assert asyncio.run(db.archive_project("nope")) is None
    assert asyncio.run(db.restore_project("nope")) is None


def test_the_archive_endpoints(board, owner):
    owner.post("/api/projects", json={"id": "gone", "name": "Gone"})
    assert owner.delete("/api/projects/gone").json() == {"id": "gone", "archived": True}
    assert "gone" not in {p["id"] for p in owner.get("/api/projects").json()}
    assert "gone" in {p["id"] for p in owner.get("/api/projects?archived=1").json()}
    assert owner.delete("/api/projects/gone").status_code == 200  # idempotent archive

    assert owner.put("/api/projects/gone/restore", json={}).json() == {"id": "gone", "archived": False}
    assert "gone" in {p["id"] for p in owner.get("/api/projects").json()}


def test_the_migration_adds_archived_at(board):
    asyncio.run(db.init_db())
    assert db.SCHEMA_VERSION >= 4
    with closing(sqlite3.connect(db.DB_PATH)) as conn:
        cols = {row[1] for row in conn.execute("PRAGMA table_info(projects)")}
        version = conn.execute("PRAGMA user_version").fetchone()[0]
    assert "archived_at" in cols
    assert version == db.SCHEMA_VERSION
