"""One live board per data folder, regardless of which port it uses."""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.request
from pathlib import Path


ROOT = Path(__file__).resolve().parent.parent


def free_port(exclude=()):
    """An unused port from the range reserved for these integration tests."""
    excluded = set(exclude)
    for port in range(49800, 49900):
        if port in excluded:
            continue
        with socket.socket() as sock:
            try:
                sock.bind(("127.0.0.1", port))
            except OSError:
                continue
        return port
    raise AssertionError("no scratch DEPARTURES port is available")


def server_environment(home):
    env = os.environ.copy()
    env["DEPARTURES_HOME"] = str(home)
    env["PYTHONPATH"] = str(ROOT) + os.pathsep + env.get("PYTHONPATH", "")
    return env


def start_server(home, port, log_name):
    home.mkdir(parents=True, exist_ok=True)
    output = open(home / log_name, "w+", encoding="utf-8")
    process = subprocess.Popen(
        [sys.executable, "-m", "departures", "--port", str(port), "--no-browser"],
        cwd=ROOT,
        env=server_environment(home),
        stdout=output,
        stderr=subprocess.STDOUT,
    )
    return process, output


def wait_until_up(process, output, port):
    deadline = time.monotonic() + 20
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output.flush()
            raise AssertionError(
                f"server exited with {process.returncode}: "
                f"{Path(output.name).read_text(encoding='utf-8')}"
            )
        try:
            with urllib.request.urlopen(
                    f"http://127.0.0.1:{port}/api/session", timeout=0.5) as response:
                if response.status == 200:
                    return
        except Exception:
            time.sleep(0.1)
    raise AssertionError(f"server did not start on scratch port {port}")


def stop_server(process, output):
    if process.poll() is None:
        process.kill()
    process.wait(timeout=10)
    output.close()


def run_seed(home, port):
    return subprocess.run(
        [sys.executable, "-m", "departures", "--port", str(port), "seed", "--yes"],
        cwd=ROOT,
        env=server_environment(home),
        capture_output=True,
        text=True,
        timeout=30,
    )


def test_live_lock_guards_seed_and_second_server_and_stale_lock_does_not(tmp_path):
    home = tmp_path / "scratch-home"
    port = free_port()
    first, first_output = start_server(home, port, "first-server.log")
    second = second_output = None
    try:
        wait_until_up(first, first_output, port)
        lock_path = home / "board.lock"
        assert lock_path.is_file()

        other_port = free_port(exclude=(port,))
        refused = run_seed(home, other_port)
        assert refused.returncode != 0
        assert "running" in (refused.stdout + refused.stderr).lower()

        second, second_output = start_server(home, other_port, "second-server.log")
        second.wait(timeout=15)
        second_output.flush()
        second_text = Path(second_output.name).read_text(encoding="utf-8")
        assert second.returncode != 0
        assert "running" in second_text.lower()
        stop_server(second, second_output)
        second = second_output = None
    finally:
        stop_server(first, first_output)
        if second is not None:
            stop_server(second, second_output)

    # Killing the server leaves its metadata file, but the OS releases the
    # lock itself. That stale file must not make the next seed refuse.
    assert (home / "board.lock").is_file()
    status = json.loads((home / "board.lock").read_text(encoding="utf-8"))
    assert status["pid"] == first.pid
    assert status["port"] == port
    assert status["startedAt"]
    recovered = run_seed(home, other_port)
    assert recovered.returncode == 0, recovered.stdout + recovered.stderr
