"""Saved Kane tests: keep secrets out of the repo, replay them after every change.

Kane CLI writes variable values into a saved test's front matter, including values marked
`secret: true`, and those values win over --variables at replay time. So Bug Whisperer removes
secret variables from the front matter entirely, and passes the real values in with --variables
when it replays the test.
"""

from __future__ import annotations

import json
import shutil
from pathlib import Path

from . import kane
from .detective import ROOT

TESTS = ROOT / ".testmuai" / "tests"


def strip_secrets(text: str) -> str:
    """Remove every front-matter variable marked `secret: true` (key line and its fields)."""
    lines = text.splitlines(keepends=True)
    out, entry = [], []

    def flush():
        if entry and not any(l.strip() == "secret: true" for l in entry):
            out.extend(entry)
        entry.clear()

    in_vars = False
    for line in lines:
        if line.startswith("variables:"):
            in_vars = True
            out.append(line)
            continue
        if in_vars and line.startswith("  ") and not line.startswith("    "):
            flush()
            entry.append(line)
        elif in_vars and line.startswith("    "):
            entry.append(line)
        else:
            if in_vars:
                flush()
                in_vars = False
            out.append(line)
    flush()
    return "".join(out)


def saved_name(name: str) -> str:
    """The name Kane really saved under. If <name> already existed, Kane adds -2, -3, ..."""
    matches = sorted(TESTS.glob(f"{name}*_test.md"), key=lambda p: p.stat().st_mtime)
    return matches[-1].name[: -len("_test.md")] if matches else name


def discard(name: str) -> None:
    """Remove a saved run that is not a regression test (for example a re-check that failed)."""
    (TESTS / f"{name}_test.md").unlink(missing_ok=True)
    shutil.rmtree(TESTS / f"output-{name}", ignore_errors=True)


def sanitize(name: str) -> Path:
    path = TESTS / f"{name}_test.md"
    path.write_text(strip_secrets(path.read_text(encoding="utf-8")), encoding="utf-8")
    return path


def replay(name: str, variables: dict, *, log_path: Path | None = None) -> kane.KaneResult:
    """Replay a saved test exactly: no adaptive heal, so a changed app fails instead of healing."""
    argv = [kane.kane_binary(), "testmd", "run", str(TESTS / f"{name}_test.md"), "--agent",
            "--headless", "--no-adaptive-heal", "--variables", json.dumps(variables)]
    return kane._execute(argv, timeout=420, log_path=log_path, on_event=None)
