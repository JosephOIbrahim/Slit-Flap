"""API correctness: a missing id is a 404, a malformed body is a 422.

Saves for something the board doesn't have used to come back 200 (the write
simply matched no row), and a body that wasn't JSON surfaced as a 500.
"""

import pytest


def test_unknown_project_is_a_404_everywhere(owner):
    assert owner.put("/api/projects/ghost", json={"name": "x"}).status_code == 404
    assert owner.delete("/api/projects/ghost").status_code == 404
    assert owner.put("/api/projects/ghost/restore", json={}).status_code == 404
    assert owner.put("/api/projects/ghost/notes", json={"content": "x"}).status_code == 404
    assert owner.get("/api/projects/ghost/notes").status_code == 404
    assert owner.post("/api/projects/ghost/logs", json={"text": "x"}).status_code == 404
    assert owner.get("/api/projects/ghost/logs").status_code == 404


def test_unknown_project_writes_change_nothing(owner):
    owner.put("/api/projects/ghost/notes", json={"content": "should not exist"})
    owner.post("/api/projects/ghost/logs", json={"text": "should not exist"})
    # No notes or logs were created for the id that wasn't there
    assert owner.get("/api/projects/ghost/notes").status_code == 404
    ids = {p["id"] for p in owner.get("/api/projects").json()}
    assert "ghost" not in ids


def test_unknown_event_is_a_404(owner):
    assert owner.put("/api/events/ghost", json={"name": "x"}).status_code == 404
    assert owner.delete("/api/events/ghost").status_code == 404


@pytest.mark.parametrize("method,path", [
    ("post", "/api/projects"),
    ("put", "/api/projects/order"),
    ("put", "/api/settings"),
    ("post", "/api/events"),
    ("post", "/api/viewers"),
])
def test_malformed_json_is_a_422(owner, method, path):
    r = getattr(owner, method)(path, content=b"{this is not json",
                               headers={"Content-Type": "application/json"})
    assert r.status_code == 422, (method, path, r.status_code)
    assert "detail" in r.json() or "error" in r.json()


@pytest.mark.parametrize("method,path", [
    ("post", "/api/projects"),
    ("put", "/api/projects/order"),
    ("put", "/api/settings"),
])
def test_a_json_body_that_is_not_an_object_is_a_422(owner, method, path):
    assert getattr(owner, method)(path, json=["not", "an", "object"]).status_code == 422


def test_valid_calls_are_unchanged(owner):
    made = owner.post("/api/projects", json={"id": "real", "name": "Real"})
    assert made.status_code == 200
    assert made.json() == {"id": "real"}

    saved = owner.put("/api/projects/real", json={"name": "Renamed"})
    assert saved.status_code == 200
    assert saved.json()["updated"] is True

    note = owner.put("/api/projects/real/notes", json={"content": "kept"})
    assert note.status_code == 200
    assert owner.get("/api/projects/real/notes").json()["content"] == "kept"

    log = owner.post("/api/projects/real/logs", json={"text": "worked"})
    assert log.status_code == 200
    assert [entry["text"] for entry in owner.get("/api/projects/real/logs").json()] == ["worked"]

    event = owner.post("/api/events", json={"time": "10:00", "name": "Standup"}).json()
    assert owner.put(f"/api/events/{event['id']}", json={"name": "Moved"}).status_code == 200
    assert owner.delete(f"/api/events/{event['id']}").status_code == 200
