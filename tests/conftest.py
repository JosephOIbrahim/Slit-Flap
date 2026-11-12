"""Shared fixtures: every test gets its own throwaway board.

Nothing here touches the real ~/.departures board. Requests run in-process
(no server, no ports); the client address decides who the app thinks is
asking: this machine (the owner) or someone else on the network.
"""

import pytest
from fastapi.testclient import TestClient

from departures import db, server

OWNER = ("127.0.0.1", 50000)        # this machine
NEIGHBOR = ("192.168.1.77", 50000)  # someone else on the same Wi-Fi

SECRET = "a file outside the frontend"


@pytest.fixture(autouse=True)
def no_real_board_probe(monkeypatch):
    """Never knock on a real port: tests are green whether or not the owner's
    board is running. Tests that need the check to say "yes" patch it again."""
    from departures import cli as cli_module
    monkeypatch.setattr(cli_module, "_board_already_running", lambda port: False)


@pytest.fixture
def board(tmp_path, monkeypatch):
    """A temporary data folder plus a fake built frontend.

    tmp_path/
      home/             <- the board's data folder (DEPARTURES_HOME)
      app/secret.txt    <- must never be served
      app/dist/         <- the "built frontend"
    """
    home = tmp_path / "home"
    monkeypatch.setattr(db, "DB_DIR", home)
    monkeypatch.setattr(db, "DB_PATH", home / "departures.db")
    monkeypatch.setattr(server, "_backups", server._Backups())  # as if freshly started
    monkeypatch.setattr(server, "_session", server._Session())  # no session yet

    app_dir = tmp_path / "app"
    dist = app_dir / "dist"
    (dist / "assets").mkdir(parents=True)
    (dist / "index.html").write_text("<!doctype html><title>DEPARTURES</title>", encoding="utf-8")
    (dist / "assets" / "board.js").write_text("console.log('board')", encoding="utf-8")
    (app_dir / "secret.txt").write_text(SECRET, encoding="utf-8")
    monkeypatch.setattr(server, "DIST_DIR", dist)
    return tmp_path


@pytest.fixture
def owner(board):
    """The owner's browser, on this machine. Starts the app (startup runs)."""
    with TestClient(server.app, client=OWNER, base_url="http://localhost:4040",
                    headers={"X-Departures": "1"}) as client:
        yield client


@pytest.fixture
def neighbor(board):
    """Someone on the same network with no invite link."""
    with TestClient(server.app, client=NEIGHBOR, base_url="http://192.168.1.10:4040",
                    headers={"X-Departures": "1"}) as client:
        yield client


@pytest.fixture
def make_viewer(owner):
    """Invite a viewer; returns (client holding their link cookie, invite)."""
    clients = []

    def _make(email="viewer@example.com"):
        invite = owner.post("/api/viewers", json={"email": email}).json()
        client = TestClient(
            server.app,
            client=NEIGHBOR,
            base_url="http://192.168.1.10:4040",
            headers={"X-Departures": "1"},
            cookies={"viewer_token": invite["token"]},
        )
        clients.append(client)
        return client, invite

    yield _make
    for client in clients:
        client.close()
