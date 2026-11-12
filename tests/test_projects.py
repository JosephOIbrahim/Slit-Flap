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


def test_two_tabs_cannot_both_create_the_same_empty_note(owner):
    owner.post("/api/projects", json={"id": "empty-note", "name": "Empty Note"})
    first_tab = owner.get("/api/projects/empty-note/notes").json()
    second_tab = owner.get("/api/projects/empty-note/notes").json()
    assert first_tab["updatedAt"] is None and second_tab["updatedAt"] is None

    first = owner.put("/api/projects/empty-note/notes",
                      json={"content": "first tab", "updatedAt": first_tab["updatedAt"]})
    second = owner.put("/api/projects/empty-note/notes",
                       json={"content": "second tab", "updatedAt": second_tab["updatedAt"]})

    assert first.status_code == 200  # both versions were null: creation is allowed
    assert second.status_code == 409  # that null is stale once the first save exists
    assert owner.get("/api/projects/empty-note/notes").json()["content"] == "first tab"


def test_the_board_reports_its_version(owner):
    from departures import __version__

    assert owner.get("/api/session").json()["version"] == __version__


def test_a_time_block_carries_its_day(owner):
    from datetime import date

    owner.post("/api/projects", json={"id": "block", "name": "Block"})
    saved = owner.put("/api/projects/block", json={
        "todayTime": "14:30", "todayDate": date.today().isoformat()}).json()
    assert saved["updated"] is True
    [block] = [p for p in owner.get("/api/projects").json() if p["id"] == "block"]
    assert block["todayTime"] == "14:30"
    assert block["todayDate"] == date.today().isoformat()


def test_a_new_event_is_for_today_unless_dated(owner):
    from datetime import date

    today = owner.post("/api/events", json={"time": "10:00", "name": "Standup"}).json()
    assert today["date"] == date.today().isoformat()

    later = owner.post("/api/events", json={"time": "11:00", "name": "Review", "date": "2099-01-01"}).json()
    assert later["date"] == "2099-01-01"


def test_the_order_endpoint_renumbers_in_one_call(owner):
    for pid in ("a", "b", "c"):
        owner.post("/api/projects", json={"id": pid, "name": pid.upper()})
    r = owner.put("/api/projects/order", json={"ids": ["c", "a", "b"]})
    assert r.status_code == 200
    order = [p["id"] for p in owner.get("/api/projects").json()]
    assert order[-3:] == ["c", "a", "b"]

    bad = owner.put("/api/projects/order", json={"ids": "c"})
    assert bad.status_code == 400


def test_a_field_save_changes_only_that_field_and_returns_the_new_version(owner):
    owner.post("/api/projects", json={"id": "p", "name": "Old", "next": "keep me", "status": "ACTIVE"})
    [before] = [p for p in owner.get("/api/projects").json() if p["id"] == "p"]

    saved = owner.put("/api/projects/p", json={"name": "New", "updatedAt": before["updatedAt"]}).json()
    assert saved["updated"] is True
    assert saved["updatedAt"]

    [after] = [p for p in owner.get("/api/projects").json() if p["id"] == "p"]
    assert after["updatedAt"] == saved["updatedAt"]  # the reply is the stored version
    assert after["name"] == "New"
    assert after["next"] == "keep me"       # only the field sent changed
    assert after["status"] == "ACTIVE"
