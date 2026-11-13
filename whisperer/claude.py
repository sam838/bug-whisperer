"""Run Claude Code headless (`claude -p`) and read its answer."""

from __future__ import annotations

import glob
import json
import os
import re
import shutil
import subprocess
from pathlib import Path


def claude_binary() -> str:
    """CLAUDE_BIN, then `claude` on PATH, then the binary bundled with the VS Code extension."""
    if os.environ.get("CLAUDE_BIN"):
        return os.environ["CLAUDE_BIN"]
    found = shutil.which("claude")
    if found:
        return found
    pattern = str(Path.home() / ".vscode" / "extensions" / "anthropic.claude-code-*" /
                  "resources" / "native-binary" / "claude*")
    candidates = sorted(glob.glob(pattern))
    if candidates:
        return candidates[-1]
    raise RuntimeError("Claude Code not found: install it or set CLAUDE_BIN")


def ask(prompt: str, *, cwd: str | Path | None = None, model: str | None = None,
        tools: str = "Read", edits: bool = False, timeout: int = 600) -> dict:
    """Run one headless Claude turn. Returns Claude Code's JSON result (with a `result` text)."""
    argv = [claude_binary(), "-p", "--output-format", "json", "--allowedTools", tools]
    if edits:
        argv += ["--permission-mode", "acceptEdits"]
    if model:
        argv += ["--model", model]
    # WHISPERER_INTERNAL: Bug Whisperer's own Claude sessions must not trigger its Stop hook.
    env = {**os.environ, "WHISPERER_INTERNAL": "1"}
    proc = subprocess.run(argv, input=prompt, capture_output=True, text=True, encoding="utf-8",
                          errors="replace", cwd=str(cwd) if cwd else None, timeout=timeout, env=env)
    try:
        return json.loads(proc.stdout)
    except json.JSONDecodeError:
        return {"is_error": True, "result": (proc.stdout or proc.stderr)[-2000:]}


def ask_json(prompt: str, **kwargs) -> dict:
    """Like ask(), but the answer must contain one JSON object, which is returned."""
    reply = ask(prompt, **kwargs)
    data = extract_json(reply.get("result", ""))
    data["_cost_usd"] = reply.get("total_cost_usd")
    return data


def extract_json(text: str) -> dict:
    fenced = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.S)
    candidate = fenced.group(1) if fenced else text[text.find("{"): text.rfind("}") + 1]
    try:
        value = json.loads(candidate)
    except json.JSONDecodeError:
        return {"_unparsed": text[-2000:]}
    return value if isinstance(value, dict) else {"_unparsed": text[-2000:]}
