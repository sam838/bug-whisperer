"""Kane's browser, live: we start Chrome, Kane CLI drives it, and we photograph its screen.

Kane CLI can attach to an existing Chrome (`--cdp-endpoint`). So for each Kane run, Bug Whisperer
starts Chrome with a DevTools port and hands that endpoint to Kane, while a background thread takes
a JPEG of Kane's current tab about once a second, written atomically to <case folder>/live.jpg.
The case page shows it while Kane works. (demo.studio, last edition's winner, filmed Kane the
same way.)

Chrome is launched through Playwright, because starting chrome.exe directly from Python didn't
open the DevTools port on Windows (chrome.exe hands off to another process and exits).

The camera never decides anything and never breaks a run: if it can't start, Kane runs headless
on its own as before, just without the live picture.
"""

from __future__ import annotations

import os
import shutil
import tempfile
import threading
import time
from pathlib import Path

PORT = int(os.environ.get("WHISPERER_CAMERA_PORT", "9333"))
INTERVAL = 0.8


def chrome_binary() -> str | None:
    candidates = [
        os.environ.get("KANE_CLI_CHROME_PATH"),  # on our server: Chrome wrapped with --no-sandbox
        r"C:\Program Files\Google\Chrome\Application\chrome.exe",
        r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
        shutil.which("google-chrome-stable"), shutil.which("google-chrome"), shutil.which("chromium"),
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
    ]
    return next((c for c in candidates if c and Path(c).exists()), None)


class KaneCamera:
    """Use as `with KaneCamera(folder) as cam: kane.run(..., cdp_endpoint=cam.endpoint)`."""

    def __init__(self, folder: Path):
        self.folder = Path(folder)
        self.endpoint: str | None = None
        self._ready = threading.Event()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._profile: str | None = None

    def __enter__(self) -> "KaneCamera":
        (self.folder / "live.jpg").unlink(missing_ok=True)  # never show the previous run's frame
        if os.environ.get("WHISPERER_NO_CAMERA") or not chrome_binary():
            return self
        self._profile = tempfile.mkdtemp(prefix="kane-chrome-")
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()
        self._ready.wait(timeout=60)  # endpoint is set only if Chrome really came up
        return self

    def __exit__(self, *exc) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=20)
        if self._profile:
            shutil.rmtree(self._profile, ignore_errors=True)

    def _run(self) -> None:
        """Owns Playwright for its whole life: Playwright objects must stay on one thread."""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            self._ready.set()
            return
        try:
            with sync_playwright() as pw:
                context = pw.chromium.launch_persistent_context(
                    self._profile, executable_path=chrome_binary(), headless=True,
                    args=[f"--remote-debugging-port={PORT}", "--remote-allow-origins=*",
                          "--disable-dev-shm-usage"],
                    viewport={"width": 1440, "height": 900})
                self.endpoint = f"http://127.0.0.1:{PORT}"
                self._ready.set()
                try:
                    self._film(context)
                finally:
                    context.close()
        except Exception:
            self.endpoint = None
        finally:
            self._ready.set()

    def _film(self, context) -> None:
        """Photograph Kane's tab over DevTools. Kane may open its tab in its own browser context,
        which Playwright's page list doesn't show, but Chrome's /json/list shows every tab."""
        import base64
        import json

        import httpx
        import websocket  # websocket-client

        target = self.folder / "live.jpg"
        ws, ws_url, msg_id = None, None, 0
        while not self._stop.is_set():
            try:
                tabs = httpx.get(f"http://127.0.0.1:{PORT}/json/list", timeout=2).json()
                web = [t for t in tabs if t.get("type") == "page" and t.get("webSocketDebuggerUrl")
                       and str(t.get("url", "")).startswith("http")]
                url = web[0]["webSocketDebuggerUrl"] if web else None  # newest-active tab first
                if url != ws_url:
                    if ws:
                        ws.close()
                    ws, ws_url = (websocket.create_connection(url, timeout=5, suppress_origin=True)
                                  if url else None), url
                if ws:
                    msg_id += 1
                    ws.send(json.dumps({"id": msg_id, "method": "Page.captureScreenshot",
                                        "params": {"format": "jpeg", "quality": 55}}))
                    reply = {}
                    while reply.get("id") != msg_id:
                        reply = json.loads(ws.recv())
                    data = (reply.get("result") or {}).get("data")
                    if data:
                        tmp = target.with_suffix(".tmp")
                        tmp.write_bytes(base64.b64decode(data))
                        os.replace(tmp, target)  # atomic: the website never reads half a picture
            except Exception:  # a tab mid-navigation or closing: reconnect next tick
                try:
                    if ws:
                        ws.close()
                except Exception:
                    pass
                ws, ws_url = None, None
            self._stop.wait(INTERVAL)
        if ws:
            try:
                ws.close()
            except Exception:
                pass
