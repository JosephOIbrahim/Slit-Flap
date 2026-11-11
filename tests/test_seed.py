"""Resetting to the demo projects: never from the web, never without
asking, never without a backup."""

import asyncio
import sqlite3
from contextlib import closing

from click.testing import CliRunner

from departures import db
from departures.cli import cli


def my_board():
    """A board with one real project on it, like the owner's own."""
    asyncio.run(db.init_db())
    asyncio.run(db.create_project({"id": "mine", "name": "My Real Project"}))


def project_ids(path=None):
    with closing(sqlite3.connect(path or db.DB_PATH)) as conn:
        return {row[0] for row in conn.execute("SELECT id FROM projects")}


def seed_backups():
    return sorted(db.backup_dir().glob("*-before-seed*.db"))


def run_seed(*args, input=None):
    return CliRunner().invoke(cli, ["seed", *args], input=input)


# ── Never from the web ──────────────────────────────────────────

def test_web_endpoint_to_wipe_the_board_is_gone(owner):
    owner.post("/api/projects", json={"id": "mine", "name": "My Real Project"})
    # Even a request a random web page could send (plain POST, no preflight)
    r = owner.post("/api/seed", content=b"", headers={
        "Origin": "https://some-other-site.example",
        "Content-Type": "text/plain",
    })
    assert r.status_code in (404, 405)
    assert "mine" in project_ids()


# ── Never without asking ────────────────────────────────────────

def test_seed_asks_first_and_no_keeps_the_board(board):
    my_board()
    result = run_seed(input="n\n")
    assert result.exit_code != 0
    assert "projects: 1" in result.output
    assert "mine" in project_ids()
    assert seed_backups() == []


def test_seed_without_a_terminal_answer_does_nothing(board):
    my_board()
    result = run_seed(input="")  # e.g. run from a script with no keyboard
    assert result.exit_code != 0
    assert "mine" in project_ids()


def test_fresh_machine_needs_no_prompt(board):
    result = run_seed()
    assert result.exit_code == 0, result.output
    assert len(project_ids()) == len(db.SEEDS)
    assert seed_backups() == []  # nothing existed to back up


# ── Never without a backup ──────────────────────────────────────

def test_seed_yes_backs_up_then_resets(board):
    my_board()
    result = run_seed(input="y\n")
    assert result.exit_code == 0, result.output

    [backup] = seed_backups()
    assert "Backup saved" in result.output and backup.name in result.output
    assert "mine" in project_ids(backup)       # the real board, safe
    assert "mine" not in project_ids()         # the live board, reset
    assert len(project_ids()) == len(db.SEEDS)


def test_yes_flag_skips_the_prompt_but_not_the_backup(board):
    my_board()
    result = run_seed("--yes")
    assert result.exit_code == 0, result.output
    assert len(seed_backups()) == 1


def test_back_to_back_resets_never_overwrite_a_backup(board):
    my_board()
    run_seed("--yes")
    run_seed("--yes")
    backups = seed_backups()
    assert len(backups) == 2
    assert sum("mine" in project_ids(b) for b in backups) == 1  # the first one survives
