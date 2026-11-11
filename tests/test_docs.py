"""The README's restore steps: the by-hand ones, done exactly as written,
work on a board that crashed with changes still in its -wal."""

import shutil
from pathlib import Path

from departures import db

from .test_backups import crash_while_writing, daily_backups, ids_in, start_board

README = Path(__file__).resolve().parent.parent / "README.md"


def restore_section() -> str:
    text = README.read_text(encoding="utf-8")
    start = text.index("**Restoring a backup.**")
    return text[start:text.index("\n---", start)]


def test_the_steps_say_how_to_stop_find_and_move_everything():
    steps = restore_section()
    for needed in (
        "netstat -ano",                  # stopping a board that has no window, by its port
        "taskkill /PID",
        "%USERPROFILE%\\.departures",    # "~" means nothing in File Explorer
        "File name extensions",          # hidden ".db" makes departures.db.db
        "departures.db.db",
        "move `departures.db`",          # moved, not copied: nothing stays behind
        "departures.db-wal",
        "departures.db-shm",
        "before-restore-2",              # a second hand restore must not reuse the folder
    ):
        assert needed in steps, needed


def test_following_the_steps_restores_cleanly_and_keeps_every_change(board):
    start_board()
    backup = db.backup_dir() / daily_backups()[0]
    crash_while_writing("DELETE FROM projects WHERE id = 'brand-refresh';"
                        "INSERT INTO projects (id, name) VALUES ('after-backup', 'After Backup');")
    data = db.DB_DIR

    # Step 3: move the board, with its -wal and -shm, into before-restore/
    kept = data / "before-restore"
    kept.mkdir()
    for name in ("departures.db", "departures.db-wal", "departures.db-shm"):
        if (data / name).exists():
            (data / name).rename(kept / name)

    # Step 4: copy the backup in and name it departures.db
    shutil.copyfile(backup, data / "departures.db")

    # Step 5: start the board
    start_board()

    assert ids_in(db.DB_PATH) == ids_in(backup)  # exactly what the backup held
    assert "after-backup" in ids_in(kept / "departures.db")  # the crash's changes, kept
