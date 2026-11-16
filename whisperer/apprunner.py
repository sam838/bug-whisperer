"""Start, restart and reset an app whose code is connected.

Why not the app's own auto-reload: on Windows, uvicorn's reloader saw the fixer's change, began
reloading, and never finished, so the old code kept serving and Kane tested it three times. So
Bug Whisperer restarts the app itself after every fix and waits until it answers.

Why reset: every Kane run creates real data (bookings, patients). The reproduction and the
re-check must start from the same state, so an optional reset command (for the sample app,
`python seed.py`) runs before each Kane run.
"""

from __future__ import annotations

import os
import re
import signal
import subprocess
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

from .detective import ROOT, App

_started: dict[str, subprocess.Popen] = {}


def _command(parts: list[str]) -> list[str]:
    # "python" in an app config means the Python running Bug Whisperer (the project's venv).
    return [sys.executable if p == "python" else p for p in parts]


def _port(app: App) -> int:
    return urlparse(app.base_url).port or 80


def is_up(app: App) -> bool:
    try:
        return httpx.get(app.base_url, timeout=3).status_code < 500
    except httpx.HTTPError:
        return False


def wait_until_up(app: App, timeout: int = 60) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if is_up(app):
            return True
        time.sleep(0.5)
    return False


def _pids_on_port(port: int) -> set[int]:
    """Processes listening on a port. Never raises: an unknown answer is an empty set."""
    try:
        if os.name == "nt":
            out = subprocess.run(["netstat", "-ano", "-p", "TCP"], capture_output=True, text=True).stdout
            return {int(m.group(1)) for m in re.finditer(rf"[:.]{port}\s+\S+\s+LISTENING\s+(\d+)", out)}
        if Path("/proc/net/tcp").exists():
            return _linux_pids_on_port(port)
        out = subprocess.run(["lsof", "-ti", f"tcp:{port}", "-sTCP:LISTEN"], capture_output=True, text=True).stdout
        return {int(p) for p in out.split()}
    except (OSError, ValueError):
        return set()


def _linux_pids_on_port(port: int) -> set[int]:
    """Read /proc directly (slim containers have no lsof): listening socket inodes → owning pids."""
    inodes = set()
    for table in ("/proc/net/tcp", "/proc/net/tcp6"):
        try:
            lines = Path(table).read_text().splitlines()[1:]
        except OSError:
            continue
        for line in lines:
            parts = line.split()
            if len(parts) > 9 and parts[3] == "0A" and int(parts[1].rsplit(":", 1)[1], 16) == port:
                inodes.add(parts[9])  # state 0A = LISTEN
    pids = set()
    for proc in Path("/proc").iterdir():
        if not proc.name.isdigit():
            continue
        try:
            for fd in (proc / "fd").iterdir():
                link = os.readlink(fd)
                if link.startswith("socket:[") and link[8:-1] in inodes:
                    pids.add(int(proc.name))
                    break
        except OSError:
            continue
    return pids


def stop(app: App) -> None:
    proc = _started.pop(app.name, None)
    if proc and proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
    for pid in _pids_on_port(_port(app)):  # also an instance someone started by hand
        try:
            if os.name == "nt":
                subprocess.run(["taskkill", "/PID", str(pid), "/T", "/F"], capture_output=True)
            else:
                os.kill(pid, signal.SIGTERM)
        except OSError:
            pass
    deadline = time.time() + 15
    while time.time() < deadline and _pids_on_port(_port(app)):
        time.sleep(0.3)


SECRET_ENV = ("LT_USERNAME", "LT_ACCESS_KEY", "KANE_USERNAME", "KANE_ACCESS_KEY", "DEMO_PASSCODE",
              "ANTHROPIC_API_KEY", "CLAUDE_CODE_OAUTH_TOKEN")


def app_env() -> dict:
    """The app runs code an AI may have edited, so it never gets Bug Whisperer's secrets."""
    return {k: v for k, v in os.environ.items() if k not in SECRET_ENV}


def start(app: App) -> bool:
    if not app.start:
        return is_up(app)
    log = open(ROOT / "runs" / f"app-{_port(app)}.log", "a", encoding="utf-8")
    _started[app.name] = subprocess.Popen(
        _command(app.start), cwd=ROOT / (app.code_dir or "."), stdout=log, stderr=subprocess.STDOUT,
        env=app_env())
    return wait_until_up(app)


def restart(app: App) -> bool:
    """Restart the app so it runs the code as it is now. Without a start command, just wait."""
    if not app.start:
        return wait_until_up(app)
    stop(app)
    return start(app)


def reset(app: App) -> None:
    """Put the app's test data back to a known state, if the app has a reset command."""
    if app.reset:
        subprocess.run(_command(app.reset), cwd=ROOT / (app.code_dir or "."), capture_output=True,
                       timeout=120, env=app_env())
