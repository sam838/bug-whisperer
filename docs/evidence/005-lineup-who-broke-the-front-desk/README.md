# Evidence 005: the Lineup. Kane names the commit that broke Bug Whisperer's front desk

**What this shows:** a real regression from Bug Whisperer's own history. Kane found **which of 41
commits** caused it, by questioning 8 versions of the app in a real browser. Each version ran its
own code, checked out from git. We didn't name the culprit, and we didn't stage anything.

## The regression (real, not staged)

On Nov 17 at 10:21, commit `8565456` **"Redesign 3d game"** quietly removed the *"Try a sample
report"* buttons from the front desk. Its name says nothing about them. A person noticed by eye,
and 8 minutes later restored them in `83d8059` *"Restored all three sample-report shortcuts"*.

The question for Kane: starting only from the symptom ("the sample report buttons are gone"), can
he find the commit that did it?

## How the Lineup works

```
python -m whisperer lineup self-sample-reports --good 430f52e --bad 8565456 --fresh
```

- **The suspects:** every commit between the first website commit (`430f52e`, Nov 13) and the
  broken one that changed `whisperer/`. There are **41**.
- **The witness check comes first:** the test must pass at the good commit and fail at the broken
  one. Otherwise no one is accused.
- **Then it bisects.** Each questioning checks out one commit in a temporary git worktree and
  starts *that* version on port 8010. Kane then runs the check *"the front desk shows a button that
  fills in a sample bug report, and clicking it fills the report box"*. A pass clears that commit
  and every one before it. A fail means the bug was already there.

## The result ([lineup.json](lineup.json))

| # | Commit | Kane | Kane's words (shortened) |
|---|---|---|---|
| 1 | `430f52e` last good | ✅ cleared | "The first sample bug report button was selected. The bug report text box was populated" |
| 2 | `8565456` broken | ❌ bug there | "a prefilled bug-report box and a submit button, but **no button for filling in a sample report**" |
| 3 | `52acb5b` suspect 20 of 41 | ✅ cleared | "A sample bug report button was available and the first one was selected" |
| 4 | `35d8ab9` suspect 30 | ✅ cleared | "The page displayed a button for filling in a sample bug report" |
| 5 | `91cb692` suspect 35 | ✅ cleared | "A sample bug report button was available and was selected" |
| 6 | `ee5f705` suspect 38 | ✅ cleared | "The bug report text box was filled successfully" |
| 7 | `d4c9535` suspect 39 | ✅ cleared | "A sample bug report button was available on the form" |
| 8 | `c90a4c3` suspect 40 | ✅ cleared | "The bug report text box was filled" |

**Culprit: `8565456` "Redesign 3d game"**, the same commit the git history points to. It took
**8 questionings for 41 suspects**, about 13 minutes, all 8 as fresh Kane runs (157 credits). Kane's
own logs for every questioning are in [kane/](kane/). On the website, the lineup is at `/lineups`, where it can also be played in 3D from this record.

Before spending any credits, we rehearsed the same lineup with a plain page check in place of Kane.
It questioned the same versions and named the same commit.

## Honesty: it took four attempts, and three of them found bugs in Bug Whisperer

| Attempt | What happened | What we changed |
|---|---|---|
| 1 ([file](attempt-1-exact-replay-no-one-accused.json)) | Exact replays only (free). On the Nov 13 page, Kane said: *"The live page is healthy, but the recording no longer recognizes its sample-report controls."* He marked it his own automation problem, so **the Lineup accused no one**. | Nothing was wrong. An exact replay is tied to the page it was recorded on, so old versions need `--fresh`: Kane checks each one from scratch with the same objective. |
| 2 ([file](attempt-2-spoiled-by-the-port-clash.json)) | **Spoiled, stopped by us.** The Claude Code Stop hook replayed today's self-checks on port 8010 while the Lineup was running an old version there, so the hook reported 3 false "reopened" checks ([hook report](hook-20261118-190535.json)). The Lineup's own first answer was taken while the hook had today's code up. Separately, at `52acb5b` Kane ran out of turns *after* every check had passed, and the run was recorded as "bug there" ([Kane's log](attempt-2-kane-ran-out-of-turns.ndjson)). | `kane.py`: a run that Kane's turn budget ended is *inconclusive*, never a failure. |
| 3 ([file](attempt-3-spoiled-by-the-port-clash.json)) | **Spoiled again.** Our first fix was a check for a running lineup, and it had a race. The hook ran before the Lineup had written its record. Kane "questioned" `430f52e` but described the buttons under *"Try a real one:"*, which is today's wording, so he was looking at today's code. | A real lock: whoever restarts and tests an app first **claims its port** (`apprunner.claim`, an atomic lock file). The other side waits, or reports "couldn't check". |
| 4 ([lineup.json](lineup.json)) | **Clean.** The hook fired during the run and, for every check, said the app was busy with the lineup instead of testing an old version ([hook report](hook-20261118-200857.json)). Kane named the culprit. | |

All of this cost about **410 credits**:

| Spent on | Credits |
|---|---|
| Recording the check | 31 |
| Spoiled attempts 2 and 3 | about 200 |
| The clean run | 157 |
| A fresh run inside one hook check | about 20 |

The false "reopened" results in the hook reports are noted as clashes in
[docs/proof/selfcheck-notes.json](../../proof/selfcheck-notes.json), so the proof doesn't count
them as caught regressions.

## Where this fits

When the Stop hook finds a closed case reopened, it now suggests the lineup command, starting from
the last commit where it saw the case hold. So a regression gets both *"it's back"* and *"this
commit did it"*, and both come from Kane.
