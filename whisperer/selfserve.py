"""A second copy of Bug Whisperer on port 8010, for Kane's self-checks (see selfcheck.py).

Started by apprunner from the whisperer/ folder (the app's code folder, so the Stop hook notices
when it changes). It serves the same pages and records but starts nothing else: no sample apps.
"""

import os
import sys
from pathlib import Path

sys.path[0] = str(Path(__file__).resolve().parent.parent)  # import the package, not its files
os.environ["WHISPERER_NO_BOOT"] = "1"

import uvicorn  # noqa: E402

uvicorn.run("whisperer.web:app", host="127.0.0.1", port=8010, log_level="warning")
