"""The phone is allowed to zoom, and the viewport is a real one."""

from pathlib import Path

INDEX = Path(__file__).resolve().parent.parent / "frontend" / "index.html"


def test_pinch_zoom_is_not_disabled():
    text = INDEX.read_text(encoding="utf-8").lower()
    assert "width=device-width" in text
    assert "user-scalable=no" not in text
    assert "maximum-scale" not in text
