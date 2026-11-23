"""Serve the demo page and open it in the default browser.

    python -m demo.serve

Regenerates `data.json`, binds to 127.0.0.1 on the first free port at or above
8765, and opens the page. Standard library only: no framework, no build step.
"""

from __future__ import annotations

import functools
import http.server
import socket
import socketserver
import sys
import threading
import webbrowser
from pathlib import Path

HERE = Path(__file__).resolve().parent
FIRST_PORT = 8765
LAST_PORT = 8800


def free_port(start: int, end: int) -> int:
    for port in range(start, end + 1):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
            probe.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            try:
                probe.bind(("127.0.0.1", port))
            except OSError:
                continue
            return port
    raise SystemExit(f"no free port in {start}-{end}")


class QuietHandler(http.server.SimpleHTTPRequestHandler):
    """Serve the demo folder and keep the console readable."""

    def log_message(self, fmt: str, *args: object) -> None:  # noqa: A003
        sys.stdout.write(f"  {self.address_string()}  {fmt % args}\n")


def main() -> int:
    # Regenerate the data so the page never shows a stale figure.
    sys.path.insert(0, str(HERE.parent))
    from demo import collect

    print("collecting facts from the repository ...")
    collect.main()
    print()

    port = free_port(FIRST_PORT, LAST_PORT)
    handler = functools.partial(QuietHandler, directory=str(HERE))
    socketserver.TCPServer.allow_reuse_address = True

    with socketserver.TCPServer(("127.0.0.1", port), handler) as httpd:
        url = f"http://127.0.0.1:{port}/index.html"
        print(f"serving {HERE}")
        print(f"open    {url}")
        print("press Ctrl+C to stop\n")
        threading.Timer(0.6, lambda: webbrowser.open(url)).start()
        try:
            httpd.serve_forever()
        except KeyboardInterrupt:
            print("\nstopped")
    return 0


if __name__ == "__main__":
    sys.exit(main())
