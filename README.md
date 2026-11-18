# 🕵️ Bug Whisperer

**Users don't write good bug reports. Kane doesn't need them to.**

Bug Whisperer turns a tester's or user's messy bug report into a reproduction a developer can't
argue with. If the app's code is connected, it also turns it into a fix that
**[Kane CLI](https://www.testmuai.com/kane-cli/)** has already proven in a real browser.

- 🌐 **Live demo:** https://bug-whisperer-tqgg.onrender.com (browse every case freely; live runs
  need the passcode in our submission)
- ▶️ **Video:** _added with the submission_
- 📊 **Every result, generated from the real records:** [docs/proof/RESULTS.md](docs/proof/RESULTS.md)
- 🛠️ **Install and use it on your own app:** [docs/SETUP.md](docs/SETUP.md)
- ⚙️ **How it works, and what we learned about Kane CLI:** [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md)

Built during the [Kane CLI Online Hackathon](https://luma.com/kanecli-online) (Nov 12–26, 2026),
with Claude Code as the coding agent. The first commit is from Nov 13.

---

## Judge it in 90 seconds

| The bar | Where to see it |
|---|---|
| **It works end to end** | A user wrote *"the system just saved it?? no warning nothing"*. Kane reproduced it, Claude repaired the code from Kane's evidence alone, and Kane passed the same steps afterwards → [evidence 001](docs/evidence/001-past-date-booking/) |
| **Kane CLI caught or proved something** | 2 real bugs caught and proven fixed, kept as Kane regression tests. 6 of 6 experiments came out as expected, [written down before they ran](docs/proof/experiments.json) → [RESULTS.md](docs/proof/RESULTS.md) |
| **Kane found who broke it** | A real regression in Bug Whisperer's own history: a commit called "Redesign 3d game" quietly removed the sample-report buttons. Kane questioned 8 of 41 commits, each running its own code, and named it → [evidence 005](docs/evidence/005-lineup-who-broke-the-front-desk/) |
| **Our agent and Kane talked to each other** | Claude repairs using only Kane's failed step, his remark and his screenshot, and only Kane can close a case. The Claude Code Stop hook blocked a session until Kane saw an old bug fixed again → [evidence 004](docs/evidence/004-hook-reopened-case/) |

Then, on the four scores:

- **Ships:** a live site, plus a one-command install for your own apps, in the terminal or on its
  website. It reads typed reports, screenshots and test-result files (Excel, CSV, XML, PDF, Word
  and more). Each case runs in real Chrome.
- **Verified:** pre-registered experiments that test whether Bug Whisperer **refuses to invent
  bugs**: a complaint that isn't a bug, a false privacy claim, a vague report, and a report with
  instructions hidden in it. 6 of 6 came out as expected.
- **Closed loop:** Kane fails → Claude repairs with Kane's evidence → Kane re-runs the same steps →
  only a pass closes the case → the saved test is replayed on every later code change (58 times so
  far) → if a case comes back, the Lineup has Kane name the commit that broke it.
- **Craft:** `bug-whisperer doctor` checks the whole setup without spending credits, and Kane
  checks Bug Whisperer itself: a check we broke on purpose was caught
  ([how](docs/HOW_IT_WORKS.md#kane-checks-bug-whisperer-itself)).

## How it works

```
Messy report, screenshot or test results
  → Claude writes it as a plain-English Kane test
  → Kane CLI runs it in real Chrome           → 🐛 Confirmed · 📂 Open · ❓ ask the user · ⚠️ inconclusive
  → Claude repairs the code, from Kane's evidence only
  → Kane replays the same steps               → ✅ case closed, only on a pass
  → the Stop hook replays the test whenever the code changes
```

A bug only counts as **fixed** when the same Kane test **failed before** the repair and **passes
after** it. Claude never decides that; Kane's verdict does. On the website, **Detective Kane** acts
out every real step in a 3D office (or a light 2D view). Nothing in the scene is invented.
More in [docs/HOW_IT_WORKS.md](docs/HOW_IT_WORKS.md).

## The proof

| | |
|---|---|
| Pre-registered experiments | **6 of 6** as expected ([experiments](docs/proof/experiments/)) |
| Case studies with full evidence | **5** ([001](docs/evidence/001-past-date-booking/), [002](docs/evidence/002-double-booking/), [003](docs/evidence/003-shop-search-any-website/), [004](docs/evidence/004-hook-reopened-case/), [005](docs/evidence/005-lineup-who-broke-the-front-desk/)) |
| Lineups: the commit that broke it, named by Kane | **1** (41 suspects, 8 questioned) |
| Bugs fixed and kept as Kane regression tests | **2** ([saved tests](.testmuai/tests/)) |
| Stop hook revisits of closed cases | **58** in 32 sessions: 54 held, 4 reopened, 0 unclear ([reports](docs/proof/revisits/)) |
| Kane CLI runs | about **76** |

- **[001](docs/evidence/001-past-date-booking/):** appointments could be booked in the past. Reproduced, repaired, proven.
- **[002](docs/evidence/002-double-booking/):** two patients could be booked into the same slot. The first repair *wasn't* proven, and the reason was Bug Whisperer's own bug (the app never reloaded). That story is in the write-up.
- **[003](docs/evidence/003-shop-search-any-website/):** a site we didn't build (LambdaTest's eCommerce Playground), with only its link.
- **[005](docs/evidence/005-lineup-who-broke-the-front-desk/):** the Lineup. Kane named the commit that removed Bug Whisperer's own sample-report buttons. It took four attempts, and the write-up says why: two of them found bugs in Bug Whisperer itself.
- **[004](docs/evidence/004-hook-reopened-case/):** the Stop hook blocked a fresh Claude Code session until it repaired a bug that had come back. (We removed the fix on purpose to stage this, and the write-up says so.)

All numbers come from `python -m whisperer proof`, which reads the real records in this repo.

## Try it

**Without installing anything:** the [live demo](https://bug-whisperer-tqgg.onrender.com) runs the
sample clinic app. Browse every case, or send Kane on a live case with the passcode.

**On your machine** (Python, Node, Chrome and Claude Code; **no Docker**):

```bash
npm install -g @testmuai/kane-cli && kane-cli login
pipx install git+https://github.com/sam838/bug-whisperer

mkdir my-cases && cd my-cases
bug-whisperer init --sample        # the sample clinic app, bugs included
bug-whisperer doctor               # checks everything, spends no Kane credits

bug-whisperer report "cant book!!! it just saved it"     # in the terminal, or…
bug-whisperer up                                         # …on the website: http://127.0.0.1:8000
```

To use it on **your own app**, even one running on `localhost`:
`bug-whisperer init --name "My Shop" --url http://localhost:3000`, plus `--code ./shop` to let it
repair bugs too. Everything else, including hosting your own copy, is in
**[docs/SETUP.md](docs/SETUP.md)**.

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

## License

[MIT](LICENSE). The 3D models and textures are CC0 (see the credits above).
