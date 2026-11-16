# JAM.md: Bug Whisperer at the Kane CLI Online Hackathon

Jam: Kane CLI Online Hackathon, TestMu AI (https://luma.com/kanecli-online)
Deadline: Nov 19, 11:59 PM IST = Nov 19, 18:29 UTC = Nov 20, 01:29 GMT+7 (confirm on Slack: an older
copy of the brief says "2 November"). Treat it as Nov 19, 23:30 GMT+7 and submit by midday Nov 19.
Upload lock: assume yes. After submitting: no pushes, turn off Render auto-deploy.

Rules: solo or team of up to 4 | any AI coding agent (Claude Code) | Kane CLI must verify the app,
and the agent and Kane must talk to each other | built during the event (first commit Nov 13,
10:30 GMT+7) | submit: public GitHub repo, 3-minute video, one paragraph, live URL or one-command
run, at least 2 public posts.
Judged: Ships, Verified, Closed loop, Craft (equal weight). Ties: Verified, then Closed loop.

Concept: You are Detective Kane: you follow a messy witness statement through the app's pages to
find the clue that proves the bug, then go back to see the fix with your own eyes.
Game rule that never bends: every game element is driven by a real Kane or Claude event. Nothing
is faked or decorative-only.

MVP (done):
- Kane's desk on the home page, RPG dialogue box with Kane's real steps, live tracker
- Case files corkboard with red string, evidence board per case, rank from cases really closed
- Intake: test results (Excel/CSV/Word/PDF/JUnit/screenshots) become one case per problem

Ship tasks (Verified and Closed loop score here, so they come first):
1. Push, clean recording run: 3 March report -> CONFIRMED -> Repair -> CASE CLOSED
2. Proof batch: 5 different reports + 1 real outside site (LambdaTest playground), results table
3. README: "Judge it in 90 seconds", "What we learned about Kane CLI", built-during-the-event line
4. Secret scan of the whole git history, then make the repo public
5. 3-minute video (Nov 18, avoid Render maintenance 09:00 GMT+7), paragraph, launch post
6. Lower DEMO_DAILY_LIMIT, freeze, submit

Stretch, in cut order (first to go is first in the list):
- Full game layer: score, levels, XP per step (cut: not real, and judges may read it as a mock)
- Hit-stop and screen shake on the verdict stamp (game-feel juice; 20 min)
- Chapter card when a case opens: "CASE #8" with the user's real words (30-45 min)
- Scene map: the app as the dungeon. Rooms = pages Kane really visited, Kane's token walks them
  live, the failed check is the red clue room, and it turns green after the repair (half a day)
- Live camera via Playwright launch: a switch in Render, no code (one test run, ~40 credits)

Timeline (GMT+7):
- Nov 16 evening: time-boxed stretch work, hard stop at 23:00. Push.
- Nov 17: ship tasks 1-4 (recording run, proof batch, README, secret scan)
- Nov 18: video (record and edit), paragraph, launch post. Feature freeze at 18:00.
- Nov 19: fix only what's broken, repo public, submit by 12:00, post.

Cut log:
- Nov 16 19:40: camera off on the server by default (it broke Kane's submit clicks; proven by the
  clinic's log). Kept as a switch to retest, not as a feature.
- Nov 16 19:40: no main menu or "Press Start" screen: it adds a click before any proof.
