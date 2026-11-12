"""JetBrains Mono ships with the board under the OFL; Disket Mono does not
ship, because its EULA forbids redistribution."""

from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FONTS = ROOT / "frontend" / "public" / "fonts"
INDEX = ROOT / "frontend" / "index.html"
APP = ROOT / "frontend" / "src" / "App.jsx"


def test_the_woff2_files_are_real_and_bundled():
    for name in ("JetBrainsMono-Regular.woff2", "JetBrainsMono-Bold.woff2"):
        data = (FONTS / name).read_bytes()
        assert data[:4] == b"wOF2", name
        assert len(data) > 20_000, name


def test_the_open_font_license_ships_with_them():
    text = (FONTS / "OFL-JetBrainsMono.txt").read_text(encoding="utf-8")
    assert "SIL Open Font License" in text


def test_the_page_declares_the_local_faces():
    html = INDEX.read_text(encoding="utf-8")
    assert '/fonts/JetBrainsMono-Regular.woff2' in html
    assert '/fonts/JetBrainsMono-Bold.woff2' in html
    assert "fonts.googleapis.com" not in html


def test_no_google_fonts_request_at_runtime():
    assert "fonts.googleapis.com" not in APP.read_text(encoding="utf-8")


def test_disket_is_not_redistributed():
    names = {p.name.lower() for p in FONTS.iterdir()}
    assert not any("disket" in name for name in names)
