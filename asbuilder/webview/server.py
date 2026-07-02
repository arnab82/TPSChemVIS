"""
Serve a bundled local copy of VibeMol (https://github.com/evangelistalab/vibemol,
MIT licensed) for QWebEngineView to load.

VibeMol is "deployable from the repository root" per its own README (a
static site, `python3 -m http.server` is literally its own quick-start
instructions) -- this just runs that same kind of server as a background
thread from inside the desktop app, on a free local port, so the bundled
copy works with no internet connection and no separate terminal.

SETUP (one-time, not part of this module): vendor a copy of VibeMol into
`asbuilder/webview/vendor/vibemol/` (e.g. `git clone --depth 1
https://github.com/evangelistalab/vibemol vendor/vibemol` and drop the
`.git` folder), keeping its LICENSE file alongside it per the MIT terms.
This module does not fetch it automatically -- no network access should be
required at app runtime.
"""

from __future__ import annotations

import functools
import http.server
import threading
from pathlib import Path

VENDORED_VIBEMOL_DIR = Path(__file__).parent / "vendor" / "vibemol"


class VibeMolServer:
    """A background HTTP server for a local static VibeMol build.

    Usage:
        server = VibeMolServer()
        server.start()
        view.load(QUrl(server.url()))
        ...
        server.stop()
    """

    def __init__(self, root: str | Path = VENDORED_VIBEMOL_DIR, port: int = 0) -> None:
        self.root = Path(root)
        if not self.root.exists():
            raise FileNotFoundError(
                f"no VibeMol build found at {self.root}. Vendor a copy first: "
                f"git clone --depth 1 https://github.com/evangelistalab/vibemol {self.root}"
            )
        self._requested_port = port
        self._httpd: http.server.ThreadingHTTPServer | None = None
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(self.root))
        self._httpd = http.server.ThreadingHTTPServer(("127.0.0.1", self._requested_port), handler)
        self._thread = threading.Thread(target=self._httpd.serve_forever, daemon=True)
        self._thread.start()

    @property
    def port(self) -> int:
        if self._httpd is None:
            raise RuntimeError("server not started")
        return self._httpd.server_address[1]

    def url(self, path: str = "/") -> str:
        return f"http://127.0.0.1:{self.port}{path}"

    def stop(self) -> None:
        if self._httpd is not None:
            self._httpd.shutdown()
            self._httpd.server_close()
            self._httpd = None
