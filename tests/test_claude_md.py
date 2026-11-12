"""CLAUDE.md is read by every agent session, so its claims about the code
must match the code. These pin the ones that had drifted."""

from pathlib import Path

CLAUDE = (Path(__file__).resolve().parent.parent / "CLAUDE.md").read_text(encoding="utf-8")


def test_port_and_data_folder_match_the_code():
    assert "8400" not in CLAUDE
    assert "localhost:4040" in CLAUDE
    assert "~/.departures" in CLAUDE
    assert "./data/" not in CLAUDE


def test_quick_start_includes_the_frontend_build():
    start = CLAUDE.index("## Quick Start")
    quick = CLAUDE[start:CLAUDE.index("\n---", start)]
    assert "pip install -e ." in quick
    assert "npm run build" in quick


def test_no_never_built_session_endpoints_listed():
    assert "POST   /api/session/start" not in CLAUDE
    assert "PUT    /api/session/end" not in CLAUDE
    assert "never built" in CLAUDE  # the note that replaced them
    assert "GET    /api/session" in CLAUDE


def test_shipped_share_mode_is_not_listed_as_unbuilt():
    assert "- User authentication" not in CLAUDE
    assert "share mode" in CLAUDE
    assert "/join/<token>" in CLAUDE
