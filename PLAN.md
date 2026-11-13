# Bug Whisperer: the plan

> **Users don't write good bug reports. Kane doesn't need them to.**

This is our plan for the Kane CLI Online Hackathon (Nov 12–19, 2026). It is written in simple
words on purpose. Update it as plans change.

---

## 1. The idea in one minute

**The boring job.** A user writes *"cant book!!! button broken 😡"*. A developer then spends
hours guessing what they meant, asking questions, clicking around to make the bug happen,
fixing it, checking the fix, and replying.

**Bug Whisperer does that job:**

1. 📩 **Report.** A user sends a messy complaint and a screenshot, from our website or from a
   "Report a problem" button inside their app.
2. 🧠 **Plan.** Claude reads the complaint and the screenshot and writes a clear test in plain
   English.
3. 🕵️ **Reproduce.** **Kane CLI** does those steps in a real Chrome browser. The result is either
   🐛 *bug confirmed*, with a screenshot, or ❓ *can't reproduce*, with one clear question to ask
   the user.
4. 🛠️ **Fix.** If the app's code is connected, Claude fixes it, using only Kane's evidence.
5. ✅ **Re-check.** Kane repeats the exact steps. If they still fail, Claude tries again (at most
   3 times), then a human is asked.
6. 💌 **Close.** The user gets a reply with proof, and the test is saved so the bug can't come back
   unnoticed.

**It works for any app, not only our sample:**

| What you connect | What you get |
|---|---|
| Only the app's link | The bug reproduced, exact steps, and a ready-made ticket |
| The link and the code | All of that, plus the fix, re-checked by Kane |

---

## 2. What we are building

| Part | What it is | Status |
|---|---|---|
| **Kane runner** (`whisperer/kane.py`) | Runs Kane and reads its NDJSON output safely | ✅ Done, 5 tests |
| **Detective** | Complaint + screenshot → Claude writes a Kane test → Kane tries to reproduce it | ⏳ Next |
| **Website: inbox** | Submit a report (text + screenshot upload + app), watch Kane work live, see the result | ⏳ |
| **Fix loop** | Claude fixes the code, Kane re-checks, at most 3 tries, then a human | ⏳ |
| **Saved tests** | Each fixed bug becomes a Kane `_test.md` that is replayed after every change | ⏳ |
| **Proof reply** | A before/after page and a message for the user | ⏳ |
| **Connect your app** | A form: name, link, optional test login, optional code location | ⏳ |
| **"Report a problem" widget** | One `<script>` line adds a report button to any website | ⏳ Stretch |
| **Bug Whisperer fixes itself** | Reports about Bug Whisperer go into Bug Whisperer | ⏳ Stretch |

### The sample apps (not the product)
- `clinic/` is a clinic booking app, our main sample. A separate Claude session built it from a
  short request ([docs/CLINIC_BUILD_PROMPT.md](docs/CLINIC_BUILD_PROMPT.md)). From now on its code
  changes **only through Bug Whisperer's fix loop**.
- A second sample of a different kind (for example a small shop) is built the same way, to show
  Bug Whisperer isn't clinic-only.

---

## 3. How it works inside

```
Report (text + screenshot + app)
   │
   ▼
Planner: Claude (headless) reads the report and the screenshot
   └─► a Kane objective: the steps, plus what SHOULD happen
           │
           ▼
Detective: kane-cli run "<objective>" --agent --headless
   ├─ Kane's check fails AND its notes match the complaint ─► 🐛 reproduced
   ├─ Kane's check passes ───────────────────────────────────► ❓ can't reproduce: ask one question
   └─ Kane couldn't run (exit 2 or 3, no result) ─────────────► ⚠️ inconclusive, never "fixed"
           │ reproduced
           ▼
Fixer: Claude Code (headless) in the app's code folder
   gets ONLY Kane's evidence: failed step, Kane's remark, what Kane saw, screenshot
           │
           ▼
App reloads ─► Kane replays the same saved test (--no-adaptive-heal)
   ├─ passes ─► ✅ fixed: proof page, reply, test kept for the future
   └─ fails ──► back to the fixer (at most 3 tries) ─► then 🙋 a human
```

**Rules that keep it honest:**
- "Fixed" needs a **failed Kane run before** and a **passing Kane run after**, on the same saved
  test.
- The fixer may change the app's code, **never the Kane tests**.
- The fixer's prompt contains Kane's evidence, never "fix bug X". Otherwise the agent could skip
  Kane.
- If Kane couldn't run, we say so. That is never a pass.

**Tech:** Python, FastAPI, Jinja and SQLite for the website; a background worker for
investigations; Kane CLI for the browser; Claude Code headless (`claude -p`) for planning and
fixing.

---

## 4. Kane CLI facts we rely on (checked on Kane CLI 0.10.4)

| Fact | Detail |
|---|---|
| Run a check | `kane-cli run "<plain English>" --agent --headless --max-steps 15 --timeout 180` |
| Read the result | The NDJSON stream ends with `run_end`. Exit codes: `0` pass, `1` fail, `2` setup error, `3` timeout |
| Values Kane saw | "store … as 'name'" in the objective puts the value in `final_state` |
| Secrets | `--variables '{"pw": {"value": "...", "secret": true}}'`. Kane masks them in its steps |
| Saved tests | `--name <flow>` saves a test. `kane-cli testmd run <file> --no-adaptive-heal` replays it |
| Another URL | `testmd run --override-start-url <url>` runs a saved test against another address |
| Cost | Measured today: one run takes about **35 credits** and **90–130 seconds**. We have about 11,000 |

---

## 5. Day by day (your time, GMT+7)

| Day | Date | Goal | Done when |
|---|---|---|---|
| 1 | **Thu Nov 13** | Kane runner ✅, sample app ✅. **The detective** works from the command line. **Kickoff post** | One messy complaint about the clinic app is reproduced by Kane, with a screenshot |
| 2 | Fri Nov 14 | **The website:** submit a report (text + screenshot), live progress, result page | A report submitted in the browser ends in "reproduced" or "can't reproduce" |
| 3 | Sat Nov 15 | **The fix loop:** Claude fixes, Kane re-checks, saved tests, proof reply | One bug goes from report to ✅ fixed, with before and after Kane runs |
| 4 | Sun Nov 16 | **Any app:** connect form, second sample app, "Report a problem" button. **Mid-week post** | A second, different app is connected and one of its bugs is reproduced |
| 5 | Mon Nov 17 | **Real reports:** run 8–10 messy reports end to end. Bug Whisperer on itself (stretch) | Evidence collected: before/after runs, a numbers table |
| 6 | Tue Nov 18 | **Make it easy to judge:** one-command start, live showcase URL, README "judge it in 90 seconds" | A judge can see a result in 30 seconds |
| 7 | **Wed Nov 19** | **Video** (3 min), **launch post**, submit **early** | Submitted, video link tested in a private window |

**Deadline:** most likely **Nov 19, 11:59 PM IST (Nov 20, 1:29 AM your time)**. The event page
has typos, so confirm on Slack.

**If we fall behind, cut in this order:** the widget → Bug Whisperer fixing itself → the live
showcase URL (keep the one-command local run). **Never cut:** the detective, the fix loop with
before/after Kane runs, honest evidence.

---

## 6. Where the bugs come from (honesty)

The clinic app came out with no security holes. Ordinary bugs (a button that does nothing, a
wrong date, a form that breaks with an emoji) are much more common, especially in **features
added later**.

1. A separate Claude session adds normal features from short requests. We record each prompt in
   `docs/`.
2. People, and we ourselves, use the apps and report real problems in messy words.
3. **Only if we have to,** we plant a bug for the demo, and the README says **exactly** which one
   and how.

---

## 7. The 3-minute video

| Time | Shot |
|---|---|
| 0:00 | A messy complaint and a blurry screenshot: *"cant book!!! button broken 😡"* |
| 0:15 | Bug Whisperer: Claude turns it into clear steps, and Kane opens Chrome and tries them live |
| 0:40 | 🐛 **Reproduced**: the user's screenshot next to Kane's screenshot of the same bug |
| 1:00 | Claude reads Kane's evidence and fixes the code |
| 1:20 | Kane repeats the exact steps: ✅ booking works. The test is saved |
| 1:40 | The user's reply with proof |
| 2:00 | "Not just our app": connect a different app in one minute, and a bug there is reproduced |
| 2:30 | A vague report Kane can't reproduce, so it asks one good question instead of guessing |
| 2:50 | *"Users don't write good bug reports. Kane doesn't need them to."* |

---

## 8. Hackathon checklist

- [ ] GitHub repo is public (`sam838/bug-whisperer`), with a README that has setup steps
- [ ] 3-minute video, YouTube **unlisted** (not private), link tested in a private window
- [ ] One paragraph: what it is, who it's for, which agent, what Kane does
- [ ] A live URL or a one-command run that shows a result in under 30 seconds
- [ ] **At least 2 public posts** (we plan 3: kickoff, mid-week, launch), with `#KaneCLIHackathon`
      and a tag for Kane CLI / TestMu AI
- [ ] Signed up on testmuai.com and ran Kane CLI ✅

## 9. Rules for us

- **Nothing about Mandira** in this project.
- **No "Co-Authored-By" lines** in commits. Commits are by `sam838`. The owner pushes.
- Only test apps we own, with test accounts. Kane does normal user actions only, with no payments.
- Never claim a feature works before Kane has shown it.
