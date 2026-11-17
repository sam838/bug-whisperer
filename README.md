# 🕵️ Bug Whisperer

**Users don't write good bug reports. Kane doesn't need them to.**

Bug Whisperer turns a tester's or user's messy bug report into a reproduction a developer can't
argue with. If the app's code is connected, it also turns it into a fix that
**[Kane CLI](https://www.testmuai.com/kane-cli/)** has already proven in a real browser.

- 🌐 **Live demo:** https://bug-whisperer-tqgg.onrender.com (browse every case freely; live runs
  need the passcode in our submission)
- ▶️ **Video:** _added with the submission_
- 📊 **Every result, generated from the real records:** [docs/proof/RESULTS.md](docs/proof/RESULTS.md)

Built during the [Kane CLI Online Hackathon](https://luma.com/kanecli-online) (Nov 12–19, 2026),
with Claude Code as the coding agent. The first commit is from Nov 13.

---

## Judge it in 90 seconds

| The bar | Where to see it |
|---|---|
| **It works end to end** | A user wrote *"the system just saved it?? no warning nothing"*. Kane reproduced it, Claude repaired the code from Kane's evidence alone, and Kane passed the same steps afterwards → [evidence 001](docs/evidence/001-past-date-booking/) |
| **Kane CLI caught or proved something** | 2 real bugs caught and proven fixed, kept as Kane regression tests. 6 of 6 experiments came out as expected, [written down before they ran](docs/proof/experiments.json) → [RESULTS.md](docs/proof/RESULTS.md) |
| **Our agent and Kane talked to each other** | Claude repairs using only Kane's failed step, his remark and his screenshot, and only Kane can close a case. The Claude Code Stop hook blocked a session until Kane saw an old bug fixed again → [evidence 004](docs/evidence/004-hook-reopened-case/) |

Then, on the four scores:

- **Ships:** a live site that reads typed reports, screenshots and test-result files (Excel, CSV,
  XML, PDF, Word and more). Each case runs in real Chrome.
- **Verified:** pre-registered experiments that test whether Bug Whisperer **refuses to invent
  bugs**: a complaint that isn't a bug, a false privacy claim, a vague report, and a report with
  instructions hidden in it. 6 of 6 came out as expected.
- **Closed loop:** Kane fails → Claude repairs with Kane's evidence → Kane re-runs the same steps →
  only a pass closes the case → the saved test is replayed on every later code change (58 times
  so far).
- **Craft:** Kane also checks Bug Whisperer itself, and a check failed on purpose to prove it can
  ([see below](#kane-checks-bug-whisperer-itself)).

## How it works

```
Messy report, screenshot or test results (.xlsx, .csv, .xml, .pdf, …)
  → Claude writes it as a plain-English Kane test (files are split into cases, one per real problem)
  → Kane CLI runs it in real Chrome
       ❌ the check fails, and Kane's own words match the report  → 🐛 Confirmed
       ✅ the check passes                                         → Open: ask the user one question
       ⚠️ Kane couldn't run, or a step never happened             → inconclusive, nothing claimed
  → if the report rests on a claim ("I can see the other clinic's patients"), Kane checks the claim too
  → (code connected) Claude repairs the app, given only Kane's evidence
  → Kane replays the same steps:  ✅ case closed   ❌ try again (at most 3)  → then a person
  → the passing test is saved, and the Stop hook replays it whenever the app's code changes
```

A bug only counts as **fixed** when the same Kane test **failed before** the repair and **passes
after** it. Claude never decides that; Kane's verdict does.

What you get for each case: the verdict, Kane's steps and screenshots, a ready-made ticket, the
repair (with the failing run before it and the passing run after it), a reply for the user, and a
case report as a PDF or Markdown.

### Detective Kane

On the website, every case is a game of detective. **Kane** walks into his 3D office, pins the
witness statement on the corkboard, sits at his computer, and acts out each real step as it
happens: the screen shows the real page and the real typed value, and every check ends in a nod
or a head shake. Nothing in the scene is invented. While Claude is working he runs small errands
around the office, and drops them the moment his browser starts. A **Simple view** button swaps
the 3D office for a light 2D version on slower computers.

## The proof

All numbers come from [`python -m whisperer proof`](docs/proof/RESULTS.md), which reads the real
records in this repo. Nothing is typed in by hand.

| | |
|---|---|
| Pre-registered experiments | **6 of 6** as expected ([experiments](docs/proof/experiments/)) |
| Case studies with full evidence | **4** ([001](docs/evidence/001-past-date-booking/), [002](docs/evidence/002-double-booking/), [003](docs/evidence/003-shop-search-any-website/), [004](docs/evidence/004-hook-reopened-case/)) |
| Bugs fixed and kept as Kane regression tests | **2** ([saved tests](.testmuai/tests/)) |
| Stop hook revisits of closed cases | **58** in 32 sessions: 54 held, 4 reopened, 0 unclear ([reports](docs/proof/revisits/)) |
| Kane CLI runs | about **68** |

- **[001](docs/evidence/001-past-date-booking/):** appointments could be booked in the past. Reproduced, repaired, proven.
- **[002](docs/evidence/002-double-booking/):** two patients could be booked into the same slot, all through the website. The first repair *wasn't* proven, and the reason was Bug Whisperer's own bug (the app never reloaded). That story is in the write-up.
- **[003](docs/evidence/003-shop-search-any-website/):** a site we didn't build (LambdaTest's eCommerce Playground), with only its link.
- **[004](docs/evidence/004-hook-reopened-case/):** the hook. A fresh Claude Code session adding an unrelated feature was blocked until it repaired a bug that had come back. (We removed the fix on purpose to stage this, and the write-up says so.)

### Kane checks Bug Whisperer itself

Bug Whisperer's own pages are saved Kane tests ([`self-*_test.md`](.testmuai/tests/)): the front
desk, the case files, a closed case, the Verified page and the case report. When a session
changes `whisperer/`, the Stop hook replays them, and the session can't finish while one fails.
To show the checks can fail, we broke the Verified page on purpose. Kane caught it (*"The /verified
address shows a 404-style missing-case page"*), and the next run passed once it was put back.

## Run it

You need Python 3.10+, Node 18+, Google Chrome, a [TestMu AI account](https://www.testmuai.com/register/)
for Kane CLI, and [Claude Code](https://docs.anthropic.com/en/docs/claude-code) (Bug Whisperer
runs it headless with `claude -p` to read reports and repair code).

```bash
npm install -g @testmuai/kane-cli
kane-cli login

python -m venv .venv
.venv\Scripts\activate             # macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt pytest
python -m pytest -q tests          # 99 tests with a fake Kane: no credits, no Chrome

uvicorn whisperer.web:app --port 8000
```

Open **http://127.0.0.1:8000**, pick a sample report (or drop in
[docs/proof/clinic-regression-run.xlsx](docs/proof/clinic-regression-run.xlsx)), and press
**Send Kane to investigate**. Bug Whisperer starts the sample clinic app on port 8001 by itself.
If `claude` isn't on your PATH, set `CLAUDE_BIN`.

From the command line:

```bash
python -m whisperer investigate apps/clinic.json "cant book in the past?? it just saved it"
python -m whisperer fix apps/clinic.json runs/<case-id>
python -m whisperer guard          # Kane revisits every closed case
python -m whisperer selfcheck      # Kane checks Bug Whisperer's own pages
python -m whisperer proof          # rebuild docs/proof/RESULTS.md from the records
```

A Kane run costs about 35 credits and takes 1.5–2 minutes, because it's a real browser doing
real steps. Replaying a saved test uses no credits.

### Connect your own app

Each app is a small JSON file in [`apps/`](apps/): its URL, its test accounts and, if you want
repairs, its code folder plus start and reset commands. See [apps/clinic.json](apps/clinic.json).
You can also add one on the website's **Apps** page.

- **Link only:** Bug Whisperer reproduces bugs and writes tickets. Works on any website.
- **Link + code:** it also repairs them, and Kane proves each repair.

Test-account passwords are sent to Kane as secret variables and never written into a test, a
log or git (`apps/secrets/` is ignored).

### The Stop hook

[.claude/settings.json](.claude/settings.json) adds a Claude Code **Stop hook**. When Claude tries
to finish work in this repo, Kane replays the closed cases for any app whose code changed. If an
old bug is back, Claude is blocked, given Kane's evidence, and has to repair it first. The hook
fails open: if Kane can't run, Claude isn't blocked, and nothing is claimed.

### The hosted demo

The same website runs on Render with Kane CLI, Chrome and Claude Code on the server
([Dockerfile](Dockerfile), [render.yaml](render.yaml)). Live runs need a passcode and have a
daily limit, connecting other apps is off, and every live case starts from the clinic app **as
its AI builder first wrote it, bugs included** ([demo/clinic_original_app.py](demo/clinic_original_app.py)),
so each judge finds the same bugs. The clinic app, which runs AI-edited code, never sees the Kane
key, the Claude token or the passcode.

To deploy your own: Render → New → Blueprint → this repo, then set `DEMO_PASSCODE`,
`LT_USERNAME`, `LT_ACCESS_KEY` and `CLAUDE_CODE_OAUTH_TOKEN` (from `claude setup-token`). Use at
least 2 GB of RAM.

## What we learned about Kane CLI

- **Read the verdict, not the vibe.** Exit code `0` passed, `1` failed, `2` setup error, `3`
  timeout. Only `0` and `1` are evidence; anything else is *inconclusive* and never counts as fixed
  or broken. Kane's NDJSON is read in one place only ([whisperer/kane.py](whisperer/kane.py)).
- **A failed check isn't always a bug.** Once, Kane "clicked" Book but the form never submitted,
  and the check failed for the wrong reason. Bug Whisperer now reads Kane's own step summary first:
  a step that didn't happen means the run proves nothing.
- **Date boxes are typed as digits, not text.** Typing `2027-11-11` into a US date box gave
  `50303-02-20`. The fix is a standing instruction file passed with `--local-context` on every run
  ([.testmuai/context.md](.testmuai/context.md)), with each example checked in real Chrome in US
  and day-first formats. Claude decides *what* to fill; Kane's context says *how* to type it.
- **"Store … as 'name'"** in an objective puts the value in `run_end.final_state`, which gives the
  judge (Claude) Kane's actual observation instead of a guess.
- **Replay with `--no-adaptive-heal`.** A regression test that heals itself can hide the very bug
  it's guarding. Saved tests here replay exactly or fail.
- **Fixed dates beat relative ones.** A test that books "tomorrow" changes every day. We re-recorded
  the double-booking test with a fixed date.
- **Kane drives local Chrome,** so it tests `localhost` directly. That's what makes the repair loop
  fast: no deploy between a fix and its proof.

## Repository

| Path | What it is |
|---|---|
| [`whisperer/`](whisperer/) | Bug Whisperer: the website, the detective, the fix loop, the hook |
| [`clinic/`](clinic/) | The sample clinic app that receives the bug reports. **Not the product.** |
| [`apps/`](apps/) | Connected apps (the clinic, LambdaTest's demo shop, and Bug Whisperer itself) |
| [`.testmuai/`](.testmuai/) | Saved Kane tests, the closed cases and Kane's standing instructions |
| [`docs/`](docs/) | Evidence from real Kane runs, the proof, and how the clinic app was built |
| [`tests/`](tests/) | 99 tests, with a fake Kane CLI: no credits, no Chrome |
| [AGENTS.md](AGENTS.md) | Rules for AI agents in this repo, including Bug Whisperer's own fixer |

## Honesty

- The clinic app was written by a **separate** Claude Code session from a short request, with no
  instructions about bugs ([prompt and session log](docs/CLINIC_BUILD_PROMPT.md)). Its bugs are its
  own. After that, `clinic/` changes only through Bug Whisperer's fix loop.
- The one staged event is evidence 004, where we removed a fix on purpose to show the hook; the
  write-up says so. The negative control on the Verified page was staged the same way.
- Saved Kane tests are never edited to make them pass. Fix the app, not the test.
- Kane checks what a user can do in a browser. Bug Whisperer is not a security scanner.

## Credits

- **[Kane CLI](https://www.testmuai.com/kane-cli/)** by TestMu AI: every reproduction and every proof.
- **[Claude Code](https://docs.anthropic.com/en/docs/claude-code)**: reads reports, plans Kane's tests and repairs code.
- **[three.js](https://threejs.org/)** r128 for the 3D office.
- **3D models and textures:** Detective Kane is the CC0 *RobotExpressive* by Tomás Laulhé
  (Quaternius), and the furniture and textures are CC0 from [Poly Haven](https://polyhaven.com/).
  Every author is listed in [whisperer/static/models/CREDITS.md](whisperer/static/models/CREDITS.md).
