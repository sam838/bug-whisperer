# 🐛 Bug Whisperer

**Users don't write good bug reports. Kane doesn't need them to.**

> Every bug report is a case. **🕵️ Kane CLI is the detective:** it goes to the scene in a real
> browser, retraces what the user did, checks the witness's claims, and only closes the case when
> it sees the fix with its own eyes. **Claude** reads the case and does the repairs, but never
> gets the last word.

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
| Detective: complaint (+ screenshot) → Kane reproduces the bug | ✅ Works from the command line ([evidence 001](docs/evidence/001-past-date-booking/)) |
| Fix loop: Claude fixes, Kane re-checks (max 3 tries, then a human) | ✅ Works from the command line ([evidence 001](docs/evidence/001-past-date-booking/)) |
| Saved regression tests, with no secrets stored, replayed with no adaptive heal | ✅ Works |
| Website: submit a report and screenshot, watch Kane live, "Fix it", before/after, reply, ticket | ✅ Works ([evidence 002](docs/evidence/002-double-booking/)) |
| Restarts the app after a fix, and resets test data before every Kane run | ✅ Works |
| **Any website:** connect an app on the Apps page (link only, or link + code). Passwords are kept out of git | ✅ Works ([evidence 003](docs/evidence/003-shop-search-any-website/): LambdaTest's demo shop) |
| **Claim double-check:** if a verdict relies on what the user claimed, Kane checks the claim too | ✅ Works |
| **🪝 The hook:** when Claude Code tries to finish, Kane revisits every closed case. If one reopened, Claude is blocked, gets Kane's evidence and repairs it | ✅ Works ([evidence 004](docs/evidence/004-hook-reopened-case/)) |
| Connect any app (link only, or link + code) | ⏳ Planned |
| "Report a problem" button for any website | ⏳ Planned |

The full plan is in [PLAN.md](PLAN.md).

**First real result:** a clinic user wrote *"the system just saved it?? no warning nothing"*. Kane
reproduced the bug (the app accepted bookings in the past), Claude fixed it from Kane's evidence
alone, Kane passed the same objective afterwards, and the saved test now replays in 20 seconds.
→ [docs/evidence/001-past-date-booking](docs/evidence/001-past-date-booking/)

**Second result, all through the website:** *"we have 2 patients booked at 10:00 tomorrow??"*
was reproduced, fixed and proven. The first fix run wasn't proven, and the reason was
Bug Whisperer's own bug (the app never reloaded). That story is in
[docs/evidence/002-double-booking](docs/evidence/002-double-booking/).

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

uvicorn whisperer.web:app --port 8000
```

Open **http://127.0.0.1:8000**. The website also starts the sample app on port 8001. Pick one of
the example reports and press **Investigate**.

Bug Whisperer also uses Claude Code headless (`claude -p`) for reading reports and fixing code. It
finds `claude` on your PATH or in the VS Code extension, or set `CLAUDE_BIN`.

From the command line:

```bash
python -m whisperer investigate apps/clinic.json "cant book in the past?? it just saved it"
python -m whisperer fix apps/clinic.json runs/<investigation-id>
```

### The hook: Kane revisits closed cases

Every case Bug Whisperer closes leaves a saved Kane test, listed in `.testmuai/closed-cases.json`.
`.claude/settings.json` adds a Claude Code **Stop hook**: whenever Claude tries to finish work in
this repo, Kane replays the closed cases for any app whose code changed. If an old bug is back,
Claude is blocked, given Kane's evidence, and has to repair it before it can finish. Run it by hand:

```bash
python -m whisperer guard          # Kane revisits every closed case
```

The hook fails open: if Kane can't run, Claude isn't blocked, and nothing is claimed. Turn it off
with `/hooks` in Claude Code.

### Connect an app

Each app is a JSON file in `apps/`: its URL, test accounts, and optionally its code folder plus
start and reset commands (see [apps/clinic.json](apps/clinic.json)). With only a URL, Bug
Whisperer reproduces bugs and writes tickets. With the code connected, it also fixes them.

### The sample app

`clinic/` is a clinic booking app. It is **not** Bug Whisperer. It's the sample app whose users
send bug reports. Logins: `sunrise@example.com` / `sunrise123` and `harbor@example.com` /
`harbor123`.

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
