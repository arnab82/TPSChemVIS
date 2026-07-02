"""
Embeds VibeMol (https://vibemol.org, MIT) via QWebEngineView for orbital
visualization -- this is the "don't build a renderer" piece of the design
doc: VibeMol parses .molden and marching-cubes the isosurfaces entirely
client-side, we just need to get a .molden file loaded into it.

TIER A (implemented here): load the molden by simulating a browser
drag-and-drop of the file onto VibeMol's own drop zone. This goes through
the exact same `drop` event VibeMol's `file-loader.js` already listens for
(its README documents "drag/drop... file ingestion" as a supported input
path), so it doesn't depend on any undocumented internal function name --
only on the drop *target* existing in the DOM, which is why
`_DROP_TARGET_SELECTOR` below is marked TODO-verify: confirm it against
VibeMol's actual index.html once it's vendored in (see webview/server.py),
since a wrong selector just means the simulated drop silently lands on the
wrong element and `molden_loaded(False)` fires.

TIER B (not implemented): a QWebChannel bridge for click-to-assign
directly on the rendered isosurface. Left as a documented extension point
(`orbital_clicked` signal below is never emitted yet) -- see the design
doc's "Tier B" section for what a fork of VibeMol would need to add
(likely a small addition to its edit-tools.js/edit-gizmos.js raycasting
path that also fires on isosurface meshes, not just atoms).
"""

from __future__ import annotations

import base64
import json
from pathlib import Path
from string import Template

from PyQt6.QtCore import QUrl, pyqtSignal
from PyQt6.QtWebEngineWidgets import QWebEngineView
from PyQt6.QtWidgets import QVBoxLayout, QWidget

from asbuilder.webview.server import VibeMolServer

# TODO-verify against the vendored VibeMol build's index.html: the element
# VibeMol's file-loader.js attaches its dragover/drop listeners to. The
# onboarding card in the live app is literally titled "Drag and drop ...
# here", which is the visible version of this element.
_DROP_TARGET_SELECTOR = "body"

_SIMULATE_DROP_JS = Template(
    """
(function(base64Data, filename, mimeType, targetSelector) {
    function b64toBlob(b64, mime) {
        const byteChars = atob(b64);
        const byteNumbers = new Array(byteChars.length);
        for (let i = 0; i < byteChars.length; i++) byteNumbers[i] = byteChars.charCodeAt(i);
        return new Blob([new Uint8Array(byteNumbers)], {type: mime});
    }
    const blob = b64toBlob(base64Data, mimeType);
    const file = new File([blob], filename, {type: mimeType});
    const dt = new DataTransfer();
    dt.items.add(file);

    const target = document.querySelector(targetSelector);
    if (!target) {
        console.error("[asbuilder] drop target not found:", targetSelector);
        return false;
    }
    const dropEvent = new DragEvent("drop", {bubbles: true, cancelable: true, dataTransfer: dt});
    target.dispatchEvent(dropEvent);
    return true;
})($b64, $filename, $mime, $selector);
"""
)


class WebViewPanel(QWidget):
    orbital_clicked = pyqtSignal(int)  # reserved for the Tier B bridge; unused for now
    molden_loaded = pyqtSignal(bool)    # emitted after the simulated-drop JS reports success/failure

    def __init__(self, vibemol_root: str | Path | None = None, parent=None) -> None:
        super().__init__(parent)
        self._server = VibeMolServer(root=vibemol_root) if vibemol_root else VibeMolServer()
        self._server.start()

        self._view = QWebEngineView(self)
        self._view.load(QUrl(self._server.url()))

        layout = QVBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.addWidget(self._view)
        self.setLayout(layout)

    def load_molden(self, molden_path: str | Path) -> None:
        """Load a .molden file into the running VibeMol page by simulating
        a drag-and-drop of it. Safe to call again after the page has
        already loaded a different file -- VibeMol's own onboarding flow
        supports loading a new file at any time."""
        data = Path(molden_path).read_bytes()
        b64 = base64.b64encode(data).decode("ascii")
        filename = Path(molden_path).name

        # json.dumps gives us safe, correctly-escaped JS string literals for
        # free (base64 payloads/filenames could in principle contain
        # characters that need escaping; don't hand-roll quoting for that).
        call = _SIMULATE_DROP_JS.substitute(
            b64=json.dumps(b64),
            filename=json.dumps(filename),
            mime=json.dumps("chemical/x-molden"),
            selector=json.dumps(_DROP_TARGET_SELECTOR),
        )
        self._view.page().runJavaScript(call, self._on_drop_result)

    def _on_drop_result(self, result) -> None:
        self.molden_loaded.emit(bool(result))

    def reload(self) -> None:
        self._view.load(QUrl(self._server.url()))

    def closeEvent(self, event) -> None:  # noqa: N802 (Qt override)
        self._server.stop()
        super().closeEvent(event)
