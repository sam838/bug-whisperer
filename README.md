# 🐛 Bug Whisperer

**Users don't write good bug reports. Kane doesn't need them to.**

Paste a messy complaint ("cant book!!! button broken 😡"), add a screenshot and the app's link.
Claude reads both and writes a plain-English test. **Kane CLI** tries it in a real browser to
reproduce the bug. If the app's code is connected, Claude fixes it and Kane runs the same steps
again until they pass. You get the bug confirmed, exact steps, a ready-made ticket, and a reply
to the user with proof.

Built for the [Kane CLI Online Hackathon](https://luma.com/kanecli-online) (Nov 12–19, 2026)
with Claude Code.

> 🚧 Work in progress: this README grows as the project does.

## Repository

| Path | What it is |
|---|---|
| `whisperer/` | Bug Whisperer: the Kane CLI runner (more coming) |
| `clinic/` | A sample app that receives bug reports. Built by a separate Claude session, see [docs/CLINIC_BUILD_PROMPT.md](docs/CLINIC_BUILD_PROMPT.md) |
| `tests/` | Tests for the Kane NDJSON parser (use a fake Kane: no credits, no Chrome) |

## Run the tests

```bash
python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install fastapi uvicorn jinja2 python-multipart pytest
python -m pytest -q tests
```

## Run the sample app

```bash
cd clinic
pip install -r requirements.txt
python seed.py
uvicorn app:app --port 8001
```

Logins: `sunrise@example.com` / `sunrise123` and `harbor@example.com` / `harbor123`.
