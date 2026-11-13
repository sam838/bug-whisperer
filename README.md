# 🐛 Bug Whisperer

**Users don't write good bug reports. Kane doesn't need them to.**

Bug Whisperer takes a messy complaint and a screenshot, such as *"cant book!!! button broken 😡"*,
and works out what the user meant. Claude turns the report into a plain-English test.
**[Kane CLI](https://www.testmuai.com/kane-cli/)** tries it in a real Chrome browser to reproduce
the bug. If the app's code is connected, Claude fixes it, and Kane repeats the exact same steps
until they pass. You get:

- the bug **confirmed** (or "can't reproduce" plus the one question to ask),
- the **exact steps** and Kane's screenshots,
- a ready-made **ticket**,
- the **fix**, with a failed Kane run before it and a passing one after it,
- a **reply** for the user, with proof,
- a saved Kane test, so the bug can't come back unnoticed.

Built for the [Kane CLI Online Hackathon](https://luma.com/kanecli-online) (Nov 12–19, 2026),
with Claude Code as the coding agent.

> 🚧 **Work in progress.** The table below says what works today. Nothing is listed as working
> before Kane has shown it working.

## Status

| Part | Status |
|---|---|
| Kane runner: runs Kane CLI and reads its NDJSON output | ✅ Works (tests in `tests/`) |
| Detective: complaint + screenshot → Kane reproduces the bug | ⏳ In progress |
| Website: submit a report, watch Kane live, see the result | ⏳ Planned |
| Fix loop: Claude fixes, Kane re-checks (max 3 tries, then a human) | ⏳ Planned |
| Connect any app (link only, or link + code) | ⏳ Planned |
| "Report a problem" button for any website | ⏳ Planned |

The full plan is in [PLAN.md](PLAN.md).

## How it works

```
Messy report + screenshot
   → Claude writes a plain-English Kane test (steps + what SHOULD happen)
   → Kane CLI runs it in real Chrome
        ❌ check fails and matches the complaint → 🐛 reproduced
        ✅ check passes                           → ❓ can't reproduce: ask the user one question
        ⚠️ Kane couldn't run                      → inconclusive (never counted as fixed)
   → (code connected) Claude fixes the app using only Kane's evidence
   → Kane replays the same saved test → ✅ fixed, or try again (max 3) → a human
```

A bug only counts as **fixed** when the same saved Kane test **failed before** the fix and
**passes after** it.

## Run it

Requirements: Python 3.10+, Node 18+, Google Chrome, and a TestMu AI account
([sign up](https://www.testmuai.com/register/)).

```bash
npm install -g @testmuai/kane-cli
kane-cli login

python -m venv .venv
.venv\Scripts\activate            # macOS/Linux: source .venv/bin/activate
pip install fastapi "uvicorn[standard]" jinja2 python-multipart httpx pytest
python -m pytest -q tests         # uses a fake Kane: no credits, no Chrome
```

### The sample app

`clinic/` is a clinic booking app. It is **not** Bug Whisperer. It's the sample app whose users
send bug reports.

```bash
cd clinic
pip install -r requirements.txt
python seed.py
uvicorn app:app --port 8001
```

Logins: `sunrise@example.com` / `sunrise123` and `harbor@example.com` / `harbor123`.

## Repository

| Path | What it is |
|---|---|
| `whisperer/` | Bug Whisperer |
| `clinic/` | The sample app that receives bug reports |
| `tests/` | Tests (no credits, no Chrome) |
| `docs/` | How the sample app was built, and evidence from real Kane runs |
| [PLAN.md](PLAN.md) | The week's plan |
| [AGENTS.md](AGENTS.md) | Rules for AI coding agents working in this repo |

## Honesty

- The clinic app was written by a separate Claude Code session from a short request. The prompt
  and the session log are in [docs/](docs/CLINIC_BUILD_PROMPT.md). After that, its code changes
  only through Bug Whisperer's fix loop.
- If we plant a bug for the demo, this README will say exactly which one and how.
- Kane checks what a user can do in a browser. Bug Whisperer is not a security scanner.
