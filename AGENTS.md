# AGENTS.md

Rules for AI coding agents working in this repository: Claude Code, Bug Whisperer's own fixer
agent, and any other agent. Humans: see [README.md](README.md) and [PLAN.md](PLAN.md).

## What this project is

**Bug Whisperer** turns a messy bug report (text + screenshot) into a bug reproduced by Kane CLI
in a real browser. Then, if the app's code is connected, it fixes the bug and re-checks it with
Kane.

- `whisperer/`: **the product.** This is where new work goes.
- `clinic/`: **a sample app, not the product.** It receives bug reports.
- `tests/`: pytest tests.
- `docs/`: build records and evidence.

## Hard rules

1. **Never edit a Kane test to make it pass.** Saved Kane tests (`*_test.md`, `.testmuai/tests/`,
   and anything under `kane/`) are the evidence. Fix the app, not the test.
2. **Never change `clinic/` by hand.** Its code changes only through Bug Whisperer's fix loop, so
   every change can be traced to a bug report. If you work on Bug Whisperer, don't "tidy up" the
   sample app.
3. **Never report something as fixed or passing without a Kane run that shows it.** If Kane
   couldn't run (exit 2 or 3, or no completion event), the result is *inconclusive*.
4. **Don't spend Kane credits in tests.** Unit tests use the fake kane-cli pattern in
   `tests/test_kane.py`. Real Kane runs only happen when a person or the fix loop asks for them.
   One run costs about 35 credits.
5. **No secrets in the repo.** Test-account passwords go to Kane as variables with
   `"secret": true`, never in objectives, logs or commits. `.env` is ignored.
6. **Commits:** short, clear messages written as the repo owner. Never add "Co-Authored-By" or any
   AI attribution line. Don't push; the owner pushes.
7. **Don't mention Mandira** anywhere in this project.

## When you are Bug Whisperer's fixer

You're given evidence from a failed Kane run: the failed step, Kane's remark, what Kane stored,
and a screenshot. Your job:

- Find the cause in the app's code and make the smallest change that fixes it.
- Change only that app's code folder. Don't touch Kane tests, Bug Whisperer, or other apps.
- Don't add new dependencies unless the fix really needs one.
- When you're done, say in one or two sentences what was wrong and what you changed. Kane will
  check your fix; you don't decide whether it worked.

## How to work here

```bash
.venv\Scripts\activate             # Windows (macOS/Linux: source .venv/bin/activate)
python -m pytest -q tests          # must pass before you finish
```

- **Python 3.10+, FastAPI, Jinja2, SQLite.** Keep functions short and names plain. Comment only
  where the reason isn't obvious.
- Kane CLI is called only through `whisperer/kane.py`. Read the verdict from `KaneResult.verdict`
  (`passed`, `failed` or `error`). Don't parse Kane's output anywhere else.
- **Windows:** this repo is developed on Windows. Use `pathlib`, not hard-coded `/` paths.
  PowerShell can't pipe a here-string to `git commit -F -`, so write the message to a file.

## Kane CLI quick reference (0.10.4)

- One check: `kane-cli run "<plain English>" --agent --headless --max-steps 15 --timeout 180`
- Exit codes: `0` passed, `1` failed, `2` setup error, `3` timeout or cancelled.
- In the objective, "store … as 'name'" puts a value in `run_end.final_state`.
- Save a run as a test with `--name <flow>`. Replay it with
  `kane-cli testmd run <file> --agent --no-adaptive-heal`.
