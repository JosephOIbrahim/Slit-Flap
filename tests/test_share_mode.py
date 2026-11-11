"""Share mode: nothing outside the built frontend is ever served, and
viewers stay read-only guests."""

import pytest

from departures import db

from .conftest import SECRET

# Request paths that try to step out of the frontend folder toward
# app/secret.txt (encoded so the HTTP client sends them untouched).
ESCAPES = [
    "/..%2Fsecret.txt",
    "/%2e%2e/secret.txt",
    "/..%5Csecret.txt",
    "/assets/..%2F..%2Fsecret.txt",
    "/assets/%2e%2e%5C%2e%2e%5Csecret.txt",
    "/join/..%2F..%2Fsecret.txt",
    "/join/x%3F/..%2F..%2Fsecret.txt",
]


# ── The board itself still works ────────────────────────────────

def test_owner_gets_the_board(owner):
    page = owner.get("/")
    assert page.status_code == 200
    assert "DEPARTURES" in page.text
    assert page.headers["cache-control"] == "no-cache"

    script = owner.get("/assets/board.js")
    assert script.status_code == 200
    assert "javascript" in script.headers["content-type"]

    # Unknown page paths still land on the board
    assert "DEPARTURES" in owner.get("/some/page").text


def test_unknown_api_path_is_a_404_not_the_board(owner):
    r = owner.get("/api/does-not-exist")
    assert r.status_code == 404
    assert r.headers["content-type"].startswith("application/json")


# ── No way out of the frontend folder ───────────────────────────

@pytest.mark.parametrize("path", ESCAPES)
def test_neighbor_without_invite_is_turned_away(neighbor, path):
    r = neighbor.get(path)
    assert r.status_code == 401
    assert SECRET not in r.text


@pytest.mark.parametrize("path", ESCAPES)
def test_viewer_cannot_escape_the_frontend(make_viewer, path):
    viewer, _ = make_viewer()
    assert SECRET not in viewer.get(path).text


@pytest.mark.parametrize("path", ESCAPES)
def test_owner_cannot_escape_the_frontend(owner, path):
    # The owner can already read their own disk; this guards against a web
    # page that tricks the owner's browser into asking.
    assert SECRET not in owner.get(path).text


def test_viewer_cannot_read_files_by_absolute_path(board, make_viewer):
    viewer, _ = make_viewer()
    secret = board / "app" / "secret.txt"
    assert SECRET not in viewer.get("/" + secret.as_posix()).text
    database = viewer.get("/" + db.DB_PATH.as_posix())
    assert b"SQLite format 3" not in database.content


def test_neighbor_cannot_reach_the_api(neighbor):
    assert neighbor.get("/api/projects").status_code == 401
    assert neighbor.get("/").status_code == 401


# ── Viewers are read-only guests ────────────────────────────────

def test_invite_link_lets_a_viewer_in(owner, neighbor):
    invite = owner.post("/api/viewers", json={"email": "friend@example.com"}).json()
    r = neighbor.get(f"/join/{invite['token']}", follow_redirects=False)
    assert r.status_code == 302
    assert "viewer_token" in r.headers["set-cookie"]
    assert neighbor.get("/").status_code == 200
    assert neighbor.get("/api/me").json()["role"] == "viewer"


def test_viewer_cannot_see_other_viewer_links(owner, make_viewer):
    viewer, _ = make_viewer("a@example.com")
    make_viewer("b@example.com")
    assert viewer.get("/api/viewers").status_code == 403
    assert len(owner.get("/api/viewers").json()) == 2


def test_viewer_cannot_change_anything(make_viewer):
    viewer, invite = make_viewer()
    assert viewer.post("/api/projects", json={"name": "X"}).status_code == 403
    assert viewer.put("/api/settings", json={"zip": "10001"}).status_code == 403
    assert viewer.delete(f"/api/viewers/{invite['id']}").status_code == 403


# ── Other web pages on this machine get nothing ─────────────────

@pytest.mark.parametrize("origin", ["http://localhost:5173", "http://localhost:3000", "http://localhost"])
def test_other_local_pages_cannot_read_the_board(owner, origin):
    # A page served from another port on this PC runs in the owner's browser,
    # so its requests arrive from 127.0.0.1. The browser only lets it read the
    # answer if the server says so with Access-Control-Allow-Origin.
    read = owner.get("/api/viewers", headers={"Origin": origin})
    assert "access-control-allow-origin" not in read.headers

    preflight = owner.options("/api/projects", headers={
        "Origin": origin,
        "Access-Control-Request-Method": "PUT",
        "Access-Control-Request-Headers": "content-type",
    })
    assert "access-control-allow-origin" not in preflight.headers
    assert "access-control-allow-credentials" not in preflight.headers
