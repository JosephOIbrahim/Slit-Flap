"""Saves must not be reported as saved when nothing was written."""

import time


def test_a_save_to_a_project_that_no_longer_exists_is_a_404(owner):
    owner.post("/api/projects", json={"id": "here", "name": "Here"})
    assert owner.put("/api/projects/here", json={"name": "Renamed"}).json()["updated"] is True

    # For example, a page left open across a restore, saving a wiped project.
    missing = owner.put("/api/projects/wiped", json={"name": "Edited After Reset"})
    assert missing.status_code == 404
    assert "No such project" in missing.text


def test_a_save_from_a_page_that_is_behind_the_board_is_refused(owner):
    # A tab left open across a restore (or another tab's save) holds an
    # older copy of the project and would write its old values back over
    # the board. Its whole-project save carries that older updatedAt.
    owner.post("/api/projects", json={"id": "tab", "name": "Tab"})
    loaded = next(p for p in owner.get("/api/projects").json() if p["id"] == "tab")

    time.sleep(0.01)  # so the next save's timestamp is definitely newer
    owner.put("/api/projects/tab", json={"name": "Saved By Another Page"})

    refused = owner.put("/api/projects/tab", json=loaded)
    assert refused.status_code == 409
    assert "Reload" in refused.text
    current = next(p for p in owner.get("/api/projects").json() if p["id"] == "tab")
    assert current["name"] == "Saved By Another Page"  # the newer save stands

    # A page that has caught up (same updatedAt) may save.
    caught_up = owner.put("/api/projects/tab", json={**loaded, "name": "Mine Again",
                                                    "updatedAt": current["updatedAt"]})
    assert caught_up.status_code == 200


def test_a_note_saved_from_a_page_that_is_behind_is_refused(owner):
    owner.post("/api/projects", json={"id": "noted", "name": "Noted"})
    assert owner.put("/api/projects/noted/notes", json={"content": "first"}).status_code == 200
    version = owner.get("/api/projects/noted/notes").json()["updatedAt"]

    assert owner.put("/api/projects/noted/notes",
                     json={"content": "second", "updatedAt": version}).status_code == 200
    late = owner.put("/api/projects/noted/notes",
                     json={"content": "from a page left open", "updatedAt": version})
    assert late.status_code == 409
    assert "changed since this page loaded" in late.text
    assert owner.get("/api/projects/noted/notes").json()["content"] == "second"


def test_the_board_reports_its_version(owner):
    from departures import __version__

    assert owner.get("/api/session").json()["version"] == __version__
