"""Saves must not be reported as saved when nothing was written."""

def test_a_save_to_a_project_that_no_longer_exists_is_a_404(owner):
    owner.post("/api/projects", json={"id": "here", "name": "Here"})
    assert owner.put("/api/projects/here", json={"name": "Renamed"}).json()["updated"] is True

    # For example, a page left open across a restore, saving a wiped project.
    missing = owner.put("/api/projects/wiped", json={"name": "Edited After Reset"})
    assert missing.status_code == 404
    assert "No such project" in missing.text
