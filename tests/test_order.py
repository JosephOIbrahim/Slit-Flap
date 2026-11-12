"""New cards land at the end, and reordering moves cards within their own slots."""

import asyncio
import sqlite3
from contextlib import closing

from departures import db


def orders():
    with closing(sqlite3.connect(db.DB_PATH)) as conn:
        return dict(conn.execute("SELECT id, sort_order FROM projects"))


def test_a_new_project_takes_the_end_of_the_board(board):
    asyncio.run(db.init_db())
    before = max(orders().values())
    asyncio.run(db.create_project({"id": "one", "name": "One"}))
    asyncio.run(db.create_project({"id": "two", "name": "Two"}))
    got = orders()
    assert got["one"] == before + 1
    assert got["two"] == before + 2


def test_a_new_project_keeps_its_time_block(board):
    asyncio.run(db.init_db())
    asyncio.run(db.create_project({"id": "block", "name": "Block",
                                   "todayTime": "14:30", "todayDate": "2026-11-12"}))
    with closing(sqlite3.connect(db.DB_PATH)) as conn:
        row = conn.execute("SELECT today_time, today_date FROM projects WHERE id = 'block'").fetchone()
    assert row == ("14:30", "2026-11-12")


def test_reordering_moves_cards_within_their_own_slots(board):
    asyncio.run(db.init_db())
    for pid in ("a", "b", "c", "d"):
        asyncio.run(db.create_project({"id": pid, "name": pid.upper()}))
    # The four new cards sit at the end, in order a, b, c, d.
    asyncio.run(db.reorder_projects(["d", "b", "c", "a"]))  # the whole visible list
    ordered = [r["id"] for r in asyncio.run(db.list_projects())]
    assert ordered[-4:] == ["d", "b", "c", "a"]
    got = orders()
    assert [got[x] for x in ("d", "b", "c", "a")] == sorted(got[x] for x in ("d", "b", "c", "a"))


def test_unknown_ids_are_ignored(board):
    asyncio.run(db.init_db())
    asyncio.run(db.create_project({"id": "a", "name": "A"}))
    result = asyncio.run(db.reorder_projects(["nope", "a"]))
    assert "nope" not in result["order"]
    assert result["order"][-1] == "a"


def test_reordering_a_subset_does_not_move_unlisted_cards(board):
    asyncio.run(db.init_db())
    for pid in ("a", "b", "c", "d"):
        asyncio.run(db.create_project({"id": pid, "name": pid.upper()}))
    asyncio.run(db.reorder_projects(["d", "b"]))  # only d and b, in that order
    ordered = [r["id"] for r in asyncio.run(db.list_projects())]
    assert ordered[-4:] == ["a", "d", "c", "b"]  # a and c kept their slots
