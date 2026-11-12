"""DNS rebinding: the board only answers to names that mean this machine.

An attacker's domain can re-resolve to 127.0.0.1, so their page's requests
arrive from this PC and look like the owner's. Accepting any Host header
would hand them the whole board; only localhost, loopback and the LAN
address printed in share mode are trusted.
"""

from fastapi.testclient import TestClient

from departures import server

from .conftest import OWNER


def test_allowed_hosts_serve_the_board(owner):
    assert owner.get("/api/projects").status_code == 200  # http://localhost:4040
    assert owner.get("/").status_code == 200


def test_a_foreign_host_is_refused(owner):
    for hostile in ("evil.example", "evil.example:4040", "127.0.0.1.evil.example"):
        r = owner.get("/api/projects", headers={"Host": hostile})
        assert r.status_code == 400, hostile
        assert "DEPARTURES" not in r.text


def test_a_foreign_host_is_refused_before_auth(owner, neighbor):
    # Even an unauthenticated visitor gets 400 (not 401, which would still
    # process the request): the host check runs first.
    assert owner.get("/", headers={"Host": "evil.example"}).status_code == 400
    assert neighbor.get("/api/projects", headers={"Host": "evil.example"}).status_code == 400


def test_share_mode_still_serves_the_board_on_the_lan_address(neighbor, make_viewer):
    # The neighbor fixture's base URL is the LAN address from the CLI banner.
    assert neighbor.get("/api/projects").status_code == 401  # right host, no invite yet
    viewer, _ = make_viewer()
    page = viewer.get("/")
    assert page.status_code == 200
    assert "DEPARTURES" in page.text


def test_this_machines_own_lan_ip_is_allowed(board, monkeypatch):
    monkeypatch.setattr(server, "_this_machines_lan_ip", lambda: "10.20.30.40")
    client = TestClient(server.app, client=OWNER, base_url="http://10.20.30.40:4040")
    with client:
        assert client.get("/api/projects").status_code == 200


def test_a_different_lan_address_is_not_trusted(owner, monkeypatch):
    monkeypatch.setattr(server, "_this_machines_lan_ip", lambda: "10.20.30.40")
    r = owner.get("/api/projects", headers={"Host": "10.20.30.41"})
    assert r.status_code == 400
