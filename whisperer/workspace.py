"""Setting up a project folder for Bug Whisperer, and checking the setup.

  bug-whisperer init --sample          the sample clinic app, bugs included, to try the whole loop
  bug-whisperer init --name … --url …  connect your own app (add --code to let it repair bugs)
  bug-whisperer doctor                 is everything installed and logged in? (spends no credits)
  bug-whisperer up                     the website
"""

from __future__ import annotations

import getpass
import json
import os
import re
import shlex
import shutil
import socket
import subprocess
import sys
from pathlib import Path

from . import camera, claude, kane
from .paths import PACKAGE, ROOT

IGNORE = ["runs/", "apps/secrets/", "*.db", "__pycache__/"]


def _sample_source() -> tuple[Path, Path, Path]:
    """(clinic folder, its app file, the AI builder's original app.py with its bugs)."""
    packed = PACKAGE / "sample"
    if packed.is_dir():  # installed: the package carries the sample
        return packed / "clinic", packed / "clinic.json", packed / "clinic" / "app.py"
    repo = PACKAGE.parent
    return repo / "clinic", repo / "apps" / "clinic.json", repo / "demo" / "clinic_original_app.py"


def _ignore_lines(folder: Path) -> None:
    """Cases, logs and passwords stay out of git."""
    path = folder / ".gitignore"
    have = path.read_text(encoding="utf-8").splitlines() if path.exists() else []
    missing = [line for line in IGNORE if line not in have]
    if missing:
        text = "\n".join(have + (["", "# Bug Whisperer"] if have else ["# Bug Whisperer"]) + missing) + "\n"
        path.write_text(text, encoding="utf-8")


def init_sample(folder: Path = ROOT) -> list[str]:
    """Copy the sample clinic app, as its AI builder first wrote it (bugs included)."""
    clinic, app_file, original = _sample_source()
    done = []
    target = folder / "clinic"
    if target.exists():
        done.append("clinic/ is already here, left as it is")
    else:
        shutil.copytree(clinic, target, ignore=shutil.ignore_patterns("__pycache__", "*.db", "*.pyc"))
        shutil.copyfile(original, target / "app.py")
        done.append("clinic/: the sample app, bugs included")
    (folder / "apps").mkdir(exist_ok=True)
    if (folder / "apps" / "clinic.json").exists():
        done.append("apps/clinic.json is already here, left as it is")
    else:
        shutil.copyfile(app_file, folder / "apps" / "clinic.json")
        done.append("apps/clinic.json: how Kane reaches it (port 8001, two test clinics)")
    (folder / "runs").mkdir(exist_ok=True)
    _ignore_lines(folder)
    return done


def slug(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-") or "app"


def init_app(name: str, url: str, *, about: str = "", code: str | None = None, start: str | None = None,
             reset: str | None = None, login_path: str = "", accounts: list[str] = (),
             folder: Path = ROOT, ask_password=getpass.getpass) -> Path:
    """Write apps/<name>.json for your own app. Test-account passwords go to apps/secrets/."""
    split = lambda cmd: shlex.split(cmd, posix=os.name != "nt") if cmd else None
    data: dict = {"name": name, "base_url": url, "about": about}
    if login_path:
        data["login_path"] = login_path
    if code:
        data["code_dir"] = code
        data["start"], data["reset"] = split(start), split(reset)
    passwords = {}
    if accounts:
        data["accounts"] = {}
        for item in accounts:
            label, _, email = item.partition("=")
            if not email:
                raise ValueError(f'--account takes LABEL=EMAIL, like "Admin=admin@example.com", not {item!r}')
            data["accounts"][label.strip()] = {"email": email.strip()}
            passwords[label.strip()] = ask_password(f"Password for the test account {email.strip()}: ")
    path = folder / "apps" / f"{slug(name)}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({k: v for k, v in data.items() if v is not None}, indent=2) + "\n", encoding="utf-8")
    if passwords:
        secrets = folder / "apps" / "secrets" / path.name
        secrets.parent.mkdir(exist_ok=True)
        secrets.write_text(json.dumps(passwords, indent=2) + "\n", encoding="utf-8")
    (folder / "runs").mkdir(exist_ok=True)
    _ignore_lines(folder)
    return path


def connected_apps(folder: Path = ROOT) -> list[str]:
    names = []
    for path in sorted((folder / "apps").glob("*.json")):
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            continue
        if not data.get("self_check"):
            names.append(data.get("name", path.stem))
    return names


def _port_free(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) != 0


def _claude_version() -> str | None:
    try:
        out = subprocess.run([claude.claude_binary(), "--version"], capture_output=True, text=True, timeout=30)
    except (RuntimeError, OSError, subprocess.TimeoutExpired):
        return None
    return out.stdout.strip().splitlines()[0] if out.returncode == 0 and out.stdout.strip() else None


def doctor(port: int = 8000) -> list[tuple[str, str, str]]:
    """Each check as (mark, what was found, how to fix it). ❌ blocks a run; ⚠️ is worth knowing."""
    checks = []
    py = ".".join(map(str, sys.version_info[:3]))
    checks.append(("✅", f"Python {py}", "") if sys.version_info >= (3, 10)
                  else ("❌", f"Python {py}", "Bug Whisperer needs Python 3.10 or newer"))
    version = kane.version()
    if not version:
        checks.append(("❌", "Kane CLI not found", "npm install -g @testmuai/kane-cli   (needs Node 18+)"))
    else:
        credits = kane.balance()
        if credits is None:
            checks.append(("❌", f"Kane CLI {version}, not logged in", "kane-cli login"))
        elif credits < 35:
            checks.append(("⚠️", f"Kane CLI {version}, {credits:,.0f} credits", "a Kane run costs about 35 credits"))
        else:
            checks.append(("✅", f"Kane CLI {version}, logged in, {credits:,.0f} credits", ""))
    claude_v = _claude_version()
    checks.append(("✅", f"Claude Code {claude_v}", "") if claude_v else
                  ("❌", "Claude Code not found", "npm install -g @anthropic-ai/claude-code, run `claude` once to log in, "
                                                  "or set CLAUDE_BIN"))
    checks.append(("✅", "Google Chrome", "") if camera.chrome_binary() else
                  ("⚠️", "Google Chrome not found where we looked", "Kane drives Chrome: install it from google.com/chrome"))
    apps = connected_apps()
    checks.append(("✅", f"{len(apps)} app(s) connected in {ROOT}: {', '.join(apps)}", "") if apps else
                  ("❌", f"No apps connected in {ROOT}", "bug-whisperer init --sample   (or --name … --url … for your own)"))
    if _port_free(port):
        checks.append(("✅", f"Port {port} is free for the website", ""))
    else:  # 8001 is the sample clinic's, so suggest one well away from it
        spare = next((p for p in (8080, 8090, 8100, 8888) if _port_free(p)), None)
        checks.append(("⚠️", f"Port {port} is in use", f"bug-whisperer up --port {spare}" if spare
                       else "stop what is using it, or pick a free port with --port"))
    return checks


def up(port: int = 8000, host: str = "127.0.0.1") -> None:
    import uvicorn
    (ROOT / "runs").mkdir(exist_ok=True)
    if not connected_apps():
        print("No apps connected yet. Try: bug-whisperer init --sample")
    print(f"Bug Whisperer: http://{host}:{port}   (cases are kept in {ROOT / 'runs'})")
    uvicorn.run("whisperer.web:app", host=host, port=port)
