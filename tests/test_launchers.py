"""The repository launchers work from UNC folders and supported Pythons."""

from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent
BAT = ROOT / "departures.bat"


def test_batch_launcher_uses_pushd_for_a_unc_repository():
    text = BAT.read_text(encoding="utf-8")
    assert 'pushd "%~dp0"' in text
    assert 'cd /d "%~dp0"' not in text
    assert "popd" in text
    assert text.index("popd") < text.rindex("exit /b")
