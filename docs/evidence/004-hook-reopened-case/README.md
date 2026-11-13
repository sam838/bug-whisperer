# Evidence 004: the hook. Kane blocks Claude Code until an old bug is fixed again

**What this shows:** a Claude Code session working on an ordinary feature was **blocked from
finishing by the Kane Stop hook**, because a bug from a closed case was back. It read Kane's
evidence, **re-prompted itself, repaired it**, and was allowed to finish only after Kane revisited
the case again and saw it closed. No person stepped in.

## Honesty: what was staged

**We removed the past-date fix ourselves, on purpose,** before starting the session, to show the
hook catching a regression. The session itself was a real, fresh, headless Claude Code session
(`claude -p`, not one of Bug Whisperer's own). It got only this request:

> In the clinic app (folder clinic/), add a small feature: on the Appointments page, show how many
> upcoming appointments there are next to the 'Upcoming' heading, like 'Upcoming (3)'. Keep the
> change small and in the existing style.

The session was told nothing about the regression, Kane or the hook.

## What happened

| Time | Event | Kane: past-date case / double-booking case |
|---|---|---|
| 14:08 | The session finishes the feature and tries to stop. **The hook blocks it** ([guard-1-blocked.json](guard-1-blocked.json)) | 🔁 **reopened** / ✅ still closed |
| | Kane's words, handed to Claude: *"The app saved Aisha's appointment for 03 Mar 2025 at 10:00 instead of rejecting the past date."* | |
| | The session repairs `validate_appointment`, putting back the past-date check | |
| 14:11 | It tries to stop again. **The hook allows it** ([guard-2-allowed.json](guard-2-allowed.json)) | ✅ still closed / ✅ still closed |

The session's own final words ([claude-session.json](claude-session.json)):

> The past-date bug is back because of the uncommitted change in `clinic/app.py` I mentioned last
> time, not because of the heading change. That change had removed the check in
> `validate_appointment` that rejects past dates. I put the check back exactly as it was in the
> last commit…

The result: the feature shipped ([feature.patch](feature.patch)), and the old bug didn't.

12 turns, about 4 minutes, $0.32 of Claude. Kane replays of saved tests use no credits.

## How the hook works

`.claude/settings.json` runs `python -m whisperer hook` whenever Claude Code tries to stop:

1. It skips Bug Whisperer's own Claude sessions (the planner and the fixer), and it skips apps
   whose code hasn't changed since every case last held. That check takes about 0.5 s.
2. Otherwise Kane replays every closed case for the app (`.testmuai/closed-cases.json`) with
   `--no-adaptive-heal`, after restarting the app and resetting its test data.
3. If a replay can't tell (for example, the page changed), a fresh Kane run of the same objective
   decides. A changed page alone is never taken as proof that a bug is back.
4. If a case reopened: `{"decision": "block", "reason": <Kane's evidence>}`. After 3 blocks in a
   row it lets Claude stop and says a person is needed.

Raw Kane replays from the blocked check: [20261113-112727-replay.ndjson](20261113-112727-replay.ndjson)
(reopened) and [20261113-124324-d930-replay.ndjson](20261113-124324-d930-replay.ndjson) (held).
