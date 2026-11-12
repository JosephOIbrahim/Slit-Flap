"""The one-live-board lock for a DEPARTURES data folder.

The file's JSON says which process owns the board; the operating-system lock
says whether that process is still alive. A crash therefore leaves useful
metadata without leaving the board permanently locked.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path


class BoardLocked(RuntimeError):
    """Another live server holds this data folder's board lock."""

    def __init__(self, path: Path):
        self.path = path
        self.info = read_lock(path)
        super().__init__(f"The board lock is held: {path}")


def lock_path() -> Path:
    from departures import db

    return db.DB_DIR / "board.lock"


def read_lock(path: Path | None = None) -> dict:
    """The last server's metadata, or {} if it is missing or incomplete."""
    path = path or lock_path()
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
        return value if isinstance(value, dict) else {}
    except (OSError, ValueError):
        return {}


def _lock(handle) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)


def _unlock(handle) -> None:
    if os.name == "nt":
        import msvcrt

        handle.seek(0)
        msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
    else:
        import fcntl

        fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def is_locked() -> bool:
    """Whether a live process holds the lock, without changing its metadata."""
    path = lock_path()
    if not path.exists():
        return False
    try:
        with open(path, "r+b") as handle:
            try:
                _lock(handle)
            except OSError:
                return True
            try:
                _unlock(handle)
            finally:
                pass
        return False
    except OSError:
        # On Windows the holder's sharing/byte lock can make the open itself
        # fail. An existing lock file that cannot be inspected must fail closed.
        return True


class BoardLock:
    """An exclusive board lock held until release or process death."""

    def __init__(self, port: int):
        self.port = port
        self.path = lock_path()
        self._handle = None

    def acquire(self) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        handle = open(self.path, "a+b")
        try:
            # msvcrt locks a byte range, so a new file needs one byte first.
            handle.seek(0, os.SEEK_END)
            if handle.tell() == 0:
                handle.write(b"\0")
                handle.flush()
            try:
                _lock(handle)
            except OSError as exc:
                raise BoardLocked(self.path) from exc

            handle.seek(0)
            handle.truncate()
            handle.write(json.dumps(
                {
                    "pid": os.getpid(),
                    "port": self.port,
                    "startedAt": datetime.now(timezone.utc).isoformat(),
                }
            ).encode("utf-8"))
            handle.flush()
            self._handle = handle
        except BaseException:
            handle.close()
            raise

    def release(self) -> None:
        handle, self._handle = self._handle, None
        if handle is None:
            return
        try:
            _unlock(handle)
        finally:
            handle.close()
