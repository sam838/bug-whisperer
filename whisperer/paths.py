"""Where Bug Whisperer keeps its work: the connected apps, the cases, the saved Kane tests.

Run from this repository, that is the repository. Installed as a package (`pipx install …`), it
is the folder you run `bug-whisperer` in, so each project keeps its own cases. BUG_WHISPERER_HOME
picks a folder explicitly.
"""

from __future__ import annotations

import os
from pathlib import Path

PACKAGE = Path(__file__).resolve().parent


def workspace() -> Path:
    home = os.environ.get("BUG_WHISPERER_HOME")
    if home:
        return Path(home).resolve()
    source = PACKAGE.parent
    if (source / "pyproject.toml").is_file() and (source / "apps").is_dir():
        return source  # running from the repository
    return Path.cwd()  # installed: the folder you run it in


ROOT = workspace()
