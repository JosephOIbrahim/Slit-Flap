"""
DEPARTURES — CLI
One command. Browser opens. You're working.
"""

import argparse
import io
import sys
import time
import threading
import webbrowser

# Force UTF-8 stdout on Windows so box-drawing characters render
if sys.stdout.encoding != "utf-8":
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding="utf-8", errors="replace")


BANNER = r"""
╔══════════════════════════════════════════════════════════╗
║                                                          ║
║   ┌─┐┌─┐┌─┐┌─┐┌─┐┌─┐┌─┐┌─┐┌─┐┌─┐┌─┐                  ║
║   │D││E││P││A││R││T││U││R││E││S││ │                  ║
║   └─┘└─┘└─┘└─┘└─┘└─┘└─┘└─┘└─┘└─┘└─┘                  ║
║                                                          ║
║   USD-COMPOSED PROJECT STATE                             ║
║   SOLARI PROTOCOL v0.4.0                                 ║
║                                                          ║
╚══════════════════════════════════════════════════════════╝
"""

AMBER = "\033[38;2;212;160;18m"
DIM = "\033[38;2;60;60;60m"
WHITE = "\033[38;2;232;228;222m"
RESET = "\033[0m"


def print_banner():
    for line in BANNER.strip().split("\n"):
        print(f"{AMBER}{line}{RESET}")
    print()


def open_browser(port: int, delay: float = 1.5):
    """Open browser after a short delay to let the server start."""
    time.sleep(delay)
    url = f"http://localhost:{port}"
    webbrowser.open(url)
    print(f"{DIM}  → Browser opened at {WHITE}{url}{RESET}")
    print(f"{DIM}  → Press Ctrl+C to stop{RESET}")
    print()


def main():
    parser = argparse.ArgumentParser(description="DEPARTURES — Project Board")
    parser.add_argument("--port", type=int, default=4040, help="Port (default: 4040)")
    parser.add_argument("--host", type=str, default="127.0.0.1", help="Host (default: 127.0.0.1)")
    parser.add_argument("--no-browser", action="store_true", help="Don't open browser")
    args = parser.parse_args()

    print_banner()
    print(f"{DIM}  Starting on platform {WHITE}{args.host}:{args.port}{RESET}")
    print()

    if not args.no_browser:
        t = threading.Thread(target=open_browser, args=(args.port,), daemon=True)
        t.start()

    try:
        import uvicorn
        uvicorn.run(
            "departures.server:app",
            host=args.host,
            port=args.port,
            log_level="warning",
            reload=False,
        )
    except KeyboardInterrupt:
        print(f"\n{DIM}  Session ended.{RESET}")
        sys.exit(0)


if __name__ == "__main__":
    main()
