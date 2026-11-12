"""The repository launchers work from UNC folders and supported Pythons."""

import os
import subprocess
import sys
from pathlib import Path

import pytest

from .test_board_lock import free_port, server_environment, wait_until_up


ROOT = Path(__file__).resolve().parent.parent
BAT = ROOT / "departures.bat"


def test_batch_launcher_uses_pushd_for_a_unc_repository():
    text = BAT.read_text(encoding="utf-8")
    assert 'pushd "%~dp0"' in text
    assert 'cd /d "%~dp0"' not in text
    assert "popd" in text
    assert text.index("popd") < text.rindex("exit /b")


@pytest.mark.skipif(sys.platform != "win32", reason="the .bat launcher is Windows-only")
def test_batch_launcher_falls_back_to_python_311(tmp_path):
    scratch = tmp_path / "launcher-copy"
    scratch.mkdir()
    port = free_port()
    copied = scratch / "departures.bat"
    copied.write_text(
        BAT.read_text(encoding="utf-8").replace(
            "%*", f"--port {port} --no-browser"
        ),
        encoding="utf-8",
    )

    # Only the fake `py -3.11` can run Python. In particular, `py -3.12`
    # and a bare `python` both fail, as they would on a machine without them.
    bin_dir = tmp_path / "fake-bin"
    bin_dir.mkdir()
    (bin_dir / "python.cmd").write_text("@echo off\nexit /b 1\n", encoding="utf-8")
    (bin_dir / "py.cmd").write_text(
        "@echo off\n"
        ">>\"%FAKE_PY_LOG%\" echo %*\n"
        "if \"%~1\"==\"-3.12\" exit /b 1\n"
        "if not \"%~1\"==\"-3.11\" exit /b 1\n"
        "\"%REAL_PYTHON%\" %2 %3 %4 %5 %6 %7 %8 %9\n"
        "exit /b %errorlevel%\n",
        encoding="utf-8",
    )

    home = tmp_path / "scratch-home"
    home.mkdir()
    env = server_environment(home)
    env["PATH"] = str(bin_dir) + os.pathsep + env.get("PATH", "")
    env["REAL_PYTHON"] = sys.executable
    env["FAKE_PY_LOG"] = str(tmp_path / "py-calls.txt")
    env["DEPARTURES_SILENT"] = "1"
    output_path = tmp_path / "launcher-output.log"
    output = open(output_path, "w+", encoding="utf-8")
    process = subprocess.Popen(
        [os.environ.get("COMSPEC", "cmd.exe"), "/d", "/c", str(copied)],
        cwd=tmp_path,
        env=env,
        stdout=output,
        stderr=subprocess.STDOUT,
    )
    try:
        wait_until_up(process, output, port)
        calls = env["FAKE_PY_LOG"] and Path(env["FAKE_PY_LOG"]).read_text(
            encoding="utf-8"
        ).splitlines()
        assert any(call.startswith("-3.12 ") for call in calls)
        assert any(call.startswith("-3.11 ") for call in calls)
        assert next(i for i, call in enumerate(calls) if call.startswith("-3.12 ")) < next(
            i for i, call in enumerate(calls) if call.startswith("-3.11 ")
        )
    finally:
        if process.poll() is None:
            # Kill only the launcher tree created by this test, including the
            # server child that a bare process.kill() on cmd.exe would orphan.
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                capture_output=True,
                timeout=10,
            )
        process.wait(timeout=10)
        output.close()
