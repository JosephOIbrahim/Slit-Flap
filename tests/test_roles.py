"""Who may do what: viewers read, the owner writes, admin routes are owner-only.

Roles are decided per route now, not by a blanket "viewers may only GET"
inside the auth middleware. Invite tokens that arrive in a URL are moved
into the cookie and stripped from the address.
"""

def test_token_in_the_url_becomes_a_cookie_and_leaves_the_url(owner, neighbor):
    invite = owner.post("/api/viewers", json={"email": "friend@example.com"}).json()
    r = neighbor.get(f"/api/projects?token={invite['token']}&archived=0",
                     follow_redirects=False)
    assert r.status_code == 302
    location = r.headers["location"]
    assert "token=" not in location
    assert "archived=0" in location  # other query parameters are kept
    cookie = r.headers["set-cookie"]
    assert "viewer_token" in cookie and "HttpOnly" in cookie

    # The cookie alone gets in from here on
    assert neighbor.get("/api/projects").status_code == 200
    assert neighbor.get("/api/me").json()["role"] == "viewer"


def test_token_on_the_board_url_is_stripped_too(owner, neighbor):
    invite = owner.post("/api/viewers", json={"email": "friend@example.com"}).json()
    r = neighbor.get(f"/?token={invite['token']}", follow_redirects=False)
    assert r.status_code == 302
    assert r.headers["location"].endswith("/")
    assert "token=" not in r.headers["location"]

    followed = neighbor.get(f"/?token={invite['token']}")
    assert followed.status_code == 200
    assert "DEPARTURES" in followed.text


def test_an_invalid_token_in_the_url_is_turned_away(neighbor):
    r = neighbor.get("/api/projects?token=not-a-real-token", follow_redirects=False)
    assert r.status_code == 401
    assert "location" not in r.headers


def test_only_the_exact_join_path_skips_auth(owner, neighbor):
    invite = owner.post("/api/viewers", json={"email": "friend@example.com"}).json()
    # A token with anything appended is not an invite link
    r = neighbor.get(f"/join/{invite['token']}/api/projects", follow_redirects=False)
    assert r.status_code == 401
    assert "viewer_token" not in r.headers.get("set-cookie", "")


def test_a_viewer_can_read_but_not_write(owner, make_viewer):
    owner.post("/api/projects", json={"id": "p", "name": "P"})
    viewer, _ = make_viewer()
    for path in ("/api/projects", "/api/events", "/api/recap", "/api/session",
                 "/api/me", "/api/projects/p/notes", "/api/projects/p/logs"):
        assert viewer.get(path).status_code == 200, path

    writes = [
        ("post", "/api/projects", {"name": "X"}),
        ("put", "/api/projects/p", {"name": "X"}),
        ("put", "/api/projects/order", {"ids": []}),
        ("delete", "/api/projects/p", None),
        ("put", "/api/projects/p/restore", None),
        ("post", "/api/projects/p/logs", {"text": "x"}),
        ("put", "/api/projects/p/notes", {"content": "x"}),
        ("post", "/api/events", {"name": "x"}),
        ("put", "/api/events/e", {"name": "x"}),
        ("delete", "/api/events/e", None),
        ("put", "/api/settings", {"zip": "10001"}),
    ]
    for method, path, body in writes:
        kwargs = {} if body is None else {"json": body}
        assert getattr(viewer, method)(path, **kwargs).status_code == 403, (method, path)


def test_admin_routes_are_owner_only(make_viewer):
    viewer, invite = make_viewer()
    assert viewer.get("/api/viewers").status_code == 403
    assert viewer.post("/api/viewers", json={"email": "new@example.com"}).status_code == 403
    assert viewer.delete(f"/api/viewers/{invite['id']}").status_code == 403
    assert viewer.get("/api/settings").status_code == 200  # display settings are shared
    assert viewer.put("/api/settings", json={"zip": "10001"}).status_code == 403


def test_the_owner_still_has_the_run_of_the_board(owner):
    assert owner.get("/api/settings").status_code == 200
    assert owner.put("/api/settings", json={"zip": "10001"}).status_code == 200
    assert owner.get("/api/viewers").status_code == 200
    assert owner.post("/api/projects", json={"id": "mine", "name": "Mine"}).status_code == 200


def test_a_viewer_gets_display_settings_but_not_the_zip(make_viewer, owner):
    owner.put("/api/settings", json={"zip": "10001", "fontSize": "140", "alignment": "center"})
    viewer, _ = make_viewer()
    seen = viewer.get("/api/settings").json()
    assert seen["fontSize"] == "140"
    assert seen["alignment"] == "center"
    assert "zip" not in seen
    assert "demo" in seen  # computed, harmless

    assert "zip" in owner.get("/api/settings").json()
