# How Bug Whisperer works

- [The loop](#the-loop)
- [Who decides what](#who-decides-what)
- [The Stop hook: closed cases stay closed](#the-stop-hook-closed-cases-stay-closed)
- [Kane checks Bug Whisperer itself](#kane-checks-bug-whisperer-itself)
- [Detective Kane](#detective-kane)
- [What we learned about Kane CLI](#what-we-learned-about-kane-cli)
- [The code](#the-code)

## The loop

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

For each case you get the verdict, Kane's steps and screenshots, a ready-made ticket (one click to
copy for GitHub or Jira), the repair with the failing run before it and the passing run after it,
a reply for the user, and a case report as a PDF or Markdown.

## Who decides what

| | Claude | Kane CLI |
|---|---|---|
| Reads the messy report and writes the test | ✅ | |
| Runs the steps in a real browser | | ✅ |
| Says whether the bug is real | Checks that Kane's failure matches the report | ✅ its failed check is the evidence |
| Repairs the code | ✅ from Kane's failed step, remark and screenshot only | |
| Says whether the repair worked | ❌ never | ✅ only a pass on the same steps closes the case |

A bug only counts as **fixed** when the same Kane test **failed before** the repair and **passes
after** it. If Kane couldn't run (exit code 2 or 3, or no completion event), the result is
*inconclusive*, never fixed and never broken.

## The Stop hook: closed cases stay closed

[.claude/settings.json](../.claude/settings.json) adds a Claude Code **Stop hook**. When Claude tries
to finish work in this repo, Kane replays the closed cases for any app whose code changed. If an old
bug is back, Claude is blocked, given Kane's evidence, and has to repair it before it can finish.
The hook fails open: if Kane can't run, Claude isn't blocked, and nothing is claimed.

So far it has replayed closed cases **58 times in 32 sessions** ([every report](proof/revisits/)).
In [evidence 004](evidence/004-hook-reopened-case/), a fresh Claude Code session adding an unrelated
feature was blocked until it repaired a bug that had come back. We removed that fix on purpose to
stage it, and the write-up says so.

## Kane checks Bug Whisperer itself

Bug Whisperer's own pages are saved Kane tests ([`self-*_test.md`](../.testmuai/tests/)): the front
desk, the case files, a closed case, the Verified page and the case report. When a session changes
`whisperer/`, the Stop hook replays them, and the session can't finish while one fails. To show the
checks can fail, we broke the Verified page on purpose. Kane caught it (*"The /verified address
shows a 404-style missing-case page"*), and the next run passed once it was put back.

## Detective Kane

On the website, every case is a game of detective. **Kane** walks into his 3D office, pins the
witness statement on the corkboard, sits at his computer, and acts out each real step as it
happens: the screen shows the real page and the real typed value, and every check ends in a nod or
a head shake, with the room glowing red when a check fails. **Nothing in the scene is invented:**
no step, no action. While Claude is working he runs small errands around the office, and drops them
the moment his browser starts. A **Simple view** button swaps the 3D office for a light 2D version
on slower computers.

## What we learned about Kane CLI

- **Read the verdict, not the vibe.** Exit code `0` passed, `1` failed, `2` setup error, `3`
  timeout. Only `0` and `1` are evidence; anything else is *inconclusive*. Kane's NDJSON is read in
  one place only ([whisperer/kane.py](../whisperer/kane.py)).
- **A failed check isn't always a bug.** Once, Kane "clicked" Book but the form never submitted, and
  the check failed for the wrong reason. Bug Whisperer now reads Kane's own step summary first: a
  step that didn't happen means the run proves nothing.
- **Date boxes are typed as digits, not text.** Typing `2027-11-11` into a US date box gave
  `50303-02-20`. The fix is a standing instruction file passed with `--local-context` on every run
  ([.testmuai/context.md](../.testmuai/context.md)), with each example checked in real Chrome in US
  and day-first formats. Claude decides *what* to fill; Kane's context says *how* to type it.
- **"Store … as 'name'"** in an objective puts the value in `run_end.final_state`, which gives the
  judge (Claude) Kane's actual observation instead of a guess.
- **Replay with `--no-adaptive-heal`.** A regression test that heals itself can hide the very bug
  it's guarding. Saved tests here replay exactly or fail.
- **Fixed dates beat relative ones.** A test that books "tomorrow" changes every day. We re-recorded
  the double-booking test with a fixed date.
- **Kane drives local Chrome,** so it tests `localhost` directly. That's what makes the repair loop
  fast: no deploy between a fix and its proof.

## The code

| Path | What it is |
|---|---|
| [`whisperer/`](../whisperer/) | Bug Whisperer: the website, the detective, the fix loop, the hook, the terminal commands |
| [`whisperer/kane.py`](../whisperer/kane.py) | The only place Kane CLI is run and its output read |
| [`clinic/`](../clinic/) | The sample clinic app that receives the bug reports. **Not the product.** |
| [`apps/`](../apps/) | Connected apps (the clinic, LambdaTest's demo shop, and Bug Whisperer itself) |
| [`.testmuai/`](../.testmuai/) | Saved Kane tests, the closed cases and Kane's standing instructions |
| [`docs/`](./) | Evidence from real Kane runs, the proof, and how the clinic app was built |
| [`tests/`](../tests/) | 117 tests, with a fake Kane CLI: no credits, no Chrome |
| [AGENTS.md](../AGENTS.md) | Rules for AI agents in this repo, including Bug Whisperer's own fixer |
