# Setting up Bug Whisperer

Run it on your own machine to use it on **your own apps**, from the terminal or from its website.
**No Docker needed.** Docker is only for hosting a shared copy on a server ([below](#host-it-on-a-server-docker)).

- [What you need](#what-you-need)
- [Install](#install)
- [Use it in the terminal](#use-it-in-the-terminal)
- [Use it on the website](#use-it-on-the-website)
- [Connect your own app](#connect-your-own-app)
- [Run it from the source](#run-it-from-the-source)
- [Host it on a server (Docker)](#host-it-on-a-server-docker)
- [When something goes wrong](#when-something-goes-wrong)

## What you need

| | Why |
|---|---|
| **Python 3.10+** | Bug Whisperer itself (the terminal commands and the website) |
| **Node 18+** and **[Kane CLI](https://www.testmuai.com/kane-cli/)** with a [TestMu AI account](https://www.testmuai.com/register/) | Kane reproduces each bug, and proves each repair, in a real browser |
| **Google Chrome** | The browser Kane drives |
| **[Claude Code](https://docs.anthropic.com/en/docs/claude-code)**, logged in | Reads the reports, plans Kane's tests and repairs the code (run headless with `claude -p`) |

No database, no cloud accounts, no `.env` file. A Kane run costs about **35 credits** and takes
1.5–2 minutes, because it's a real browser doing real steps. Replaying a saved test, and
`bug-whisperer doctor`, use no credits.

## Install

```bash
npm install -g @testmuai/kane-cli && kane-cli login
pipx install git+https://github.com/sam838/bug-whisperer      # or: pip install git+https://…

mkdir my-cases && cd my-cases
bug-whisperer init --sample        # the sample clinic app, bugs included
bug-whisperer doctor               # checks everything, spends no Kane credits
```

`doctor` says exactly what's missing and how to fix it:

```
✅ Python 3.12.4
✅ Kane CLI 0.10.4, logged in, 9,029 credits
✅ Claude Code 2.1.325
✅ Google Chrome
✅ 1 app(s) connected in C:\my-cases: Clinic Records
✅ Port 8000 is free for the website
```

The folder you run it in holds your connected apps (`apps/`), your cases (`runs/`) and the Kane
tests that keep closed bugs closed. `init` adds the cases, logs and passwords to `.gitignore`.

The sample is a clinic booking app **as its AI builder first wrote it, bugs included**, so you can
watch the whole loop on your machine: Kane reproduces a bug, Claude repairs it, Kane proves it.
Bug Whisperer starts it on port 8001 by itself.

## Use it in the terminal

```bash
bug-whisperer report "hi. my receptionist booked mrs aisha for 3 march 2025 by accident and it just saved it??"
```

You follow the case live: what Claude is doing, then each step Kane takes in the browser in plain
words (`·` done, `✗` a check that failed), then the verdict: **🐛 CONFIRMED** with a ready-made
ticket, **📂 OPEN**, **❓** the one question to ask the user, or **⚠️ INCONCLUSIVE** when Kane
couldn't finish. If the bug is confirmed and the code is connected, it asks *"Repair it now?"*,
and Kane re-runs the same steps to prove the repair.

A real run on the sample app, from a fresh `pipx` install (Nov 17; `…` marks steps left out here):

```
━━ Case 20261117-152922-9e58 · Clinic Records

🧠 Claude is reading the report and writing Kane's orders…
🕵️  Kane is at the scene, in a real Chrome browser:
   · I went to http://127.0.0.1:8051/login.
   …
   · I picked Aisha Rahman in Patient.
   · I typed 2025-03-03 into Date.
   · I typed 10:30 into Time.
   · I clicked Book appointment button to book the appointment.
   …
   ✗ I checked: the appointment was not saved and the page shows an error saying the date cannot.
⚖️  Kane found something. Claude is checking it matches the report…

🐛 CONFIRMED  Kane logged in and filled in the booking form for Aisha Rahman with a date of 3 March
   2025, which is in the past. When it clicked Book appointment, the app saved the booking and moved
   to her patient page. It showed no warning, which is the problem the clinic reported.
   Ticket: Appointments can be booked with a past date and are saved without any error
   …

━━ Repairing case 20261117-152922-9e58: Claude works from Kane's evidence only, then Kane checks.

🛠️  fixing (attempt 1)
🛠️  waiting for the app to reload (attempt 1)
🛠️  Kane re-checking (attempt 1)
   · I went to http://127.0.0.1:8051/login.
   …
   · I clicked Book appointment button.
   · I checked: the appointment was not saved and the page shows an error saying the date cannot.

✅ CASE CLOSED  Kane repeated the same steps and saw the fix with his own eyes.
   The passing test is saved, and replayed whenever this app's code changes.
```

The repair Claude made, from Kane's evidence alone:

```diff
 def validate_appointment(appt_date: str, appt_time: str) -> list[str]:
     errors = []
     try:
-        date.fromisoformat(appt_date)
+        if date.fromisoformat(appt_date) < date.today():
+            errors.append("Appointment date cannot be in the past.")
```

More commands:

| Command | What it does |
|---|---|
| `bug-whisperer report --file results.xlsx` | A tester's results (Excel, CSV, XML, PDF, Word, screenshots…): one case per failure, run one after another |
| `bug-whisperer repair <case>` | Repair a confirmed case later |
| `bug-whisperer cases` | The cases on file, newest first |
| `bug-whisperer guard` | Kane revisits every closed case: is any old bug back? |
| `--repair` / `--no-repair` | Skip the *"Repair it now?"* question, for scripts |
| `--app <name>` | Which app, when more than one is connected |

## Use it on the website

```bash
bug-whisperer up                   # http://127.0.0.1:8000
```

Your own copy of the website, with nothing turned off: the same cases with Detective Kane acting
them out in 3D, the evidence board, before-and-after screenshots, a PDF case report, and the
**Apps** page for connecting apps. Cases started in the terminal show up here too, and the terminal
prints each case's link. Pick a sample report (or drop in
[clinic-regression-run.xlsx](proof/clinic-regression-run.xlsx)) and press **Send Kane to investigate**.
On a slower computer, the **Simple view** button swaps the 3D office for a light 2D one.

## Connect your own app

```bash
bug-whisperer init --name "My Shop" --url http://localhost:3000 \
  --login-path /login --account "Admin=admin@shop.test" \
  --code ./shop --start "npm start" --reset "npm run seed"
```

| | Bug Whisperer can |
|---|---|
| **Link only** (leave out `--code`) | Reproduce bugs and write tickets. Any website, even one you don't own, even `localhost` |
| **Link + code** | Also repair them, with Kane proving each repair |

- `--start` starts your app and `--reset` puts its test data back before every Kane run, both run
  in the `--code` folder. Leave them out if your app is already running and needs no reset.
- The test account's password is asked for, sent to Kane as a **secret variable**, and kept in
  `apps/secrets/`. It never goes into the app file, a test, a log or git.
- `init` writes a small JSON file in `apps/` ([apps/clinic.json](../apps/clinic.json) is the
  sample's). You can edit it, or add apps on the website's **Apps** page instead.

## Run it from the source

```bash
git clone https://github.com/sam838/bug-whisperer && cd bug-whisperer
python -m venv .venv
.venv\Scripts\activate             # macOS/Linux: source .venv/bin/activate
pip install -e ".[dev]"
python -m pytest -q tests          # 117 tests with a fake Kane: no credits, no Chrome
bug-whisperer up                   # from the repository, it uses the repository's apps and cases
python -m whisperer selfcheck      # Kane checks Bug Whisperer's own pages
python -m whisperer proof          # rebuild docs/proof/RESULTS.md from the records
```

## Host it on a server (Docker)

Only for a shared copy on a server, like our [live demo](https://bug-whisperer-tqgg.onrender.com).
The image ([Dockerfile](../Dockerfile)) holds Bug Whisperer, Kane CLI with Chrome, Claude Code and
the sample clinic. On Render: **New → Blueprint →** this repo ([render.yaml](../render.yaml)), then set:

| Variable | What it is |
|---|---|
| `DEMO_PASSCODE` | The passcode visitors type before Kane runs or a repair starts |
| `LT_USERNAME`, `LT_ACCESS_KEY` | Your TestMu AI account, for Kane CLI |
| `CLAUDE_CODE_OAUTH_TOKEN` | From `claude setup-token` |
| `DEMO_DAILY_LIMIT` | Live runs per day (default 20), so credits can't run away |

Use at least 2 GB of RAM. In this hosted mode, connecting other apps is turned off, every live
case starts from the clinic as its AI builder first wrote it (so each visitor finds the same
bugs), and the clinic, which runs AI-edited code, never sees the Kane key, the Claude token or the
passcode.

## When something goes wrong

Start with `bug-whisperer doctor`: it checks everything below and spends no credits.

| You see | Do this |
|---|---|
| ❌ Kane CLI not found / not logged in | `npm install -g @testmuai/kane-cli`, then `kane-cli login` |
| ❌ Claude Code not found | Install it and run `claude` once to log in, or set `CLAUDE_BIN` to its path |
| ⚠️ Port 8000 is in use | `bug-whisperer up --port 8080` |
| The sample clinic won't start | Something else is on port 8001. Stop it, or change both `8001`s in `apps/clinic.json` |
| ⚠️ **INCONCLUSIVE** | Kane couldn't finish (a setup error or a timeout), so nothing is claimed. Check `kane-cli balance` and that the app is up, then run it again |
| ❓ It asked the user a question | The report didn't say enough to test. Add the missing detail and run it again |
