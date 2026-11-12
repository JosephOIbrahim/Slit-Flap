"""Share mode: nothing outside the built frontend is ever served, and
viewers stay read-only guests."""

import os
from pathlib import Path

import pytest

from fastapi.testclient import TestClient

from departures import db
from departures import server

from .conftest import OWNER, SECRET

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


def test_files_with_unusual_names_are_served(board, owner):
    dist = board / "app" / "dist"
    (dist / "assets" / "logo@2x.png").write_bytes(b"PNG-BYTES")
    (dist / "assets" / "my font (bold)~1.woff2").write_bytes(b"FONT-BYTES")
    assert owner.get("/assets/logo@2x.png").content == b"PNG-BYTES"
    assert owner.get("/assets/my%20font%20(bold)~1.woff2").content == b"FONT-BYTES"


def test_a_missing_file_is_a_404_not_the_board(owner):
    for path in ("/assets/gone-123.js", "/favicon.ico", "/assets/board.js.map"):
        r = owner.get(path)
        assert r.status_code == 404, path
        assert "DEPARTURES" not in r.text
    assert "DEPARTURES" in owner.get("/some/page").text  # page paths still get the board


def test_head_requests_work(owner):
    r = owner.head("/assets/board.js")
    assert r.status_code == 200
    assert r.content == b""
    assert int(r.headers["content-length"]) == len("console.log('board')")
    assert owner.head("/").status_code == 200


def test_browsers_reuse_files_they_already_have(board, owner):
    # Built assets carry a content hash in their name, so a browser may keep
    # them for good. The page is checked each time; unchanged costs a 304.
    script = owner.get("/assets/board.js")
    assert script.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert owner.get("/assets/board.js", headers={"If-None-Match": script.headers["etag"]}).status_code == 304

    page = owner.get("/")
    for check in ({"If-None-Match": page.headers["etag"]},
                  {"If-None-Match": f'"other", W/{page.headers["etag"]}'},
                  {"If-Modified-Since": page.headers["last-modified"]}):
        unchanged = owner.get("/", headers=check)
        assert unchanged.status_code == 304, check
        assert unchanged.content == b""
        assert unchanged.headers["etag"] == page.headers["etag"]
        assert unchanged.headers["cache-control"] == "no-cache"
    assert owner.get("/", headers={"If-Modified-Since": "not a date"}).status_code == 200

    # After a rebuild, a browser holding the old page gets the new one in full.
    (board / "app" / "dist" / "index.html").write_text(
        "<!doctype html><title>DEPARTURES</title><p>rebuilt</p>", encoding="utf-8")
    rebuilt = owner.get("/", headers={"If-None-Match": page.headers["etag"]})
    assert rebuilt.status_code == 200
    assert "rebuilt" in rebuilt.text


def test_request_paths_never_reach_the_filesystem(owner, monkeypatch):
    # Files are matched against a list the server makes itself. Record every
    # stat and path lookup during requests aimed outside the frontend: none
    # may carry the request's own path.
    touched = []
    real_stat, real_lstat, real_realpath = os.stat, os.lstat, os.path.realpath

    def spy(real):
        def wrapper(path, *args, **kwargs):
            touched.append(str(path))
            return real(path, *args, **kwargs)
        return wrapper

    monkeypatch.setattr(os, "stat", spy(real_stat))
    monkeypatch.setattr(os, "lstat", spy(real_lstat))
    monkeypatch.setattr(os.path, "realpath", spy(real_realpath))
    for probe in ("/assets/MARKER-1.js", "/C:/MARKER-2/x.txt", "/..%2FMARKER-3.txt",
                  "//MARKER-4/share/x.txt", "/CON", "/assets/%2e%2e%5CMARKER-5.txt"):
        owner.get(probe)
    assert not [p for p in touched if "MARKER" in p or p.endswith("CON")]


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


def test_a_write_without_the_board_header_is_refused(board):
    # A page on another site can POST without reading the answer, but it
    # cannot add a custom header without a preflight this board never grants.
    client = TestClient(server.app, client=OWNER, base_url="http://localhost:4040")
    with client:
        r = client.post("/api/projects", json={"id": "csrf", "name": "CSRF"})
        assert r.status_code == 403
        assert "X-Departures" in r.text
        assert client.get("/api/projects").status_code == 200  # reads are open
