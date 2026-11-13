"""The detective: a messy bug report goes in, a Kane CLI reproduction comes out.

1. Plan:      Claude reads the report (and screenshot) and writes a Kane objective. The objective
              ends by verifying what SHOULD happen, so a failed check means the bug is real.
2. Reproduce: Kane CLI runs the objective in a real Chrome browser.
3. Judge:     if Kane's check failed, Claude compares Kane's evidence with the complaint, because
              a failure can also mean Kane got lost. Kane errors are never judged: inconclusive.
"""

from __future__ import annotations

import json
import secrets
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from urllib.parse import urljoin

from . import claude, evidence, kane

ROOT = Path(__file__).resolve().parent.parent
RUNS = ROOT / "runs"


@dataclass
class App:
    name: str
    base_url: str
    login_path: str = ""
    accounts: dict = field(default_factory=dict)  # label -> {"email", "password"}
    code_dir: str | None = None
    about: str = ""
    start: list | None = None  # command that starts the app, run in code_dir ("python" = this venv)
    reset: list | None = None  # command that resets the app's test data, run in code_dir

    @classmethod
    def load(cls, path: str | Path) -> "App":
        path = Path(path)
        data = json.loads(path.read_text(encoding="utf-8"))
        # Passwords of apps connected through the website live in apps/secrets/ (never committed).
        secrets_file = path.parent / "secrets" / path.name
        if secrets_file.exists():
            passwords = json.loads(secrets_file.read_text(encoding="utf-8"))
            for label, acct in data.get("accounts", {}).items():
                if label in passwords:
                    acct["password"] = passwords[label]
        return cls(**data)

    def variables(self) -> dict:
        out = {}
        for i, (_, acct) in enumerate(self.accounts.items(), start=1):
            out[f"account{i}_email"] = {"value": acct["email"], "secret": False}
            out[f"account{i}_password"] = {"value": acct["password"], "secret": True}
        return out

    def account_hints(self) -> str:
        if not self.accounts:
            return "The app needs no login."
        lines = [f"- {label}: email {{{{account{i}_email}}}}, password {{{{account{i}_password}}}}"
                 for i, label in enumerate(self.accounts, start=1)]
        login = urljoin(self.base_url, self.login_path) if self.login_path else self.base_url
        return f"Login page: {login}\nTest accounts (use these placeholders exactly):\n" + "\n".join(lines)


def new_id() -> str:
    return time.strftime("%Y%m%d-%H%M%S") + "-" + secrets.token_hex(2)


@dataclass
class Investigation:
    report: str
    app: str
    screenshot: str | None = None
    id: str = field(default_factory=new_id)
    app_file: str | None = None
    created: str = field(default_factory=lambda: time.strftime("%Y-%m-%d %H:%M"))
    status: str = "planning"  # planning, reproducing, judging, done
    verdict: str | None = None  # reproduced, not_reproduced, needs_info, inconclusive
    plan: dict = field(default_factory=dict)
    kane: dict = field(default_factory=dict)
    judgement: dict = field(default_factory=dict)
    attempts: list = field(default_factory=list)
    fix: dict = field(default_factory=dict)
    fix_history: list = field(default_factory=list)  # earlier fix runs, kept as evidence
    claim: dict = field(default_factory=dict)  # Kane's double-check of a claim the verdict relied on
    note: str = ""  # a person's note on the case, e.g. that it was re-investigated as another case
    guard: list = field(default_factory=list)  # Kane's later revisits of this closed case

    @property
    def folder(self) -> Path:
        path = RUNS / self.id
        path.mkdir(parents=True, exist_ok=True)
        return path

    def save(self) -> None:
        (self.folder / "investigation.json").write_text(
            json.dumps(asdict(self), indent=2, default=str), encoding="utf-8")


PLAN_PROMPT = """You help reproduce bug reports. A user of the web app below sent a messy report.
Turn it into ONE test for Kane CLI, a browser agent that follows plain-English instructions.

App: {name} at {base_url}
{about}
{accounts}

The user's report:
<report>
{report}
</report>
{screenshot}
Reply with ONLY a JSON object:
{{
  "understanding": "one sentence: what the user most likely did and what went wrong",
  "enough_info": true or false,
  "question": "if enough_info is false: the ONE question to ask the user; else empty",
  "expected": "what the app SHOULD do (the correct behaviour)",
  "objective": "the Kane objective, see rules"
}}

Rules for the objective:
- Start at a full URL. If a login is needed, log in with the placeholders above, written exactly
  like {{{{account1_email}}}}. Never write real passwords.
- Then the user's steps, concretely: which page, which fields, which exact values, which button.
- No "if" or "for example": choose every value yourself. Fewer words means fewer steps for Kane.
- Dates: write exact dates (YYYY-MM-DD), never "today" or "tomorrow". Unless the report is about a
  specific date, pick one well in the future (at least a year ahead), so the steps still mean the
  same thing when they are replayed months later.
- Then: "Store what the page shows after that as 'what_happened'."
- End with ONE check: "Verify that <the correct behaviour>." It must FAIL if the bug is real.
- Only normal user actions. At most 8 actions.
{feedback}"""

RETRY_FEEDBACK = """
A previous attempt with this objective did not finish, so its result says nothing about the bug:
<previous_objective>
{objective}
</previous_objective>
What went wrong, in Kane's own words: {kane_summary}
{judge_note}
Write a shorter, more direct objective that avoids that problem.
"""

JUDGE_PROMPT = """A user reported a bug. A browser agent (Kane CLI) tried to reproduce it, and its
final check failed. Decide whether the failure shows the user's bug, or whether the agent just got
lost (wrong page, could not find a field, login failed, and so on).

User's report:
<report>
{report}
</report>

What we expected: {expected}
Kane's objective: {objective}
Kane's result: {result}

Reply with ONLY a JSON object:
{{
  "reproduced": true or false,
  "agent_lost": true if the run ended before it could show anything about the bug, else false,
  "explanation": "one or two plain sentences for a non-developer",
  "claim_check": "see below, or empty",
  "ticket": {{"title": "...", "steps": ["..."], "expected": "...", "actual": "..."}}
}}

claim_check: if your verdict relies on something the user CLAIMED that Kane did not show (for
example "you sell Canon cameras", "it worked yesterday", "my account has 3 orders"), write ONE
short Kane objective that checks that claim in the app: start at a full URL, at most 4 actions,
end with "Verify that <the claim is true>." Use the same login placeholders as the objective
above. If the verdict doesn't rely on such a claim, leave it empty. Don't rely on your own memory
of the app: if you're tempted to, that's exactly what claim_check is for.
"""


MAX_ATTEMPTS = 2


def investigate(app: App, report: str, screenshot: str | None = None,
                on_update=None, inv: Investigation | None = None) -> Investigation:
    inv = inv or Investigation(report=report, app=app.name, screenshot=screenshot)
    notify = on_update or (lambda _inv: None)

    def step(status: str) -> None:
        inv.status = status
        inv.save()
        notify(inv)

    step("planning")
    shot = (f"\nThe user also attached a screenshot. Look at it with the Read tool: {screenshot}\n"
            if screenshot else "")
    feedback = ""
    for attempt in range(1, MAX_ATTEMPTS + 1):
        if attempt > 1:
            step("re-planning")
        inv.plan = claude.ask_json(PLAN_PROMPT.format(
            name=app.name, base_url=app.base_url, about=app.about, accounts=app.account_hints(),
            report=report, screenshot=shot, feedback=feedback))
        if not inv.plan.get("objective") or inv.plan.get("enough_info") is False:
            inv.verdict = "needs_info"
            break

        step("reproducing")
        from . import apprunner  # imported here: apprunner imports this module
        apprunner.reset(app)
        if not apprunner.is_up(app):
            apprunner.start(app)
        result = kane.run(inv.plan["objective"], variables=app.variables(), max_steps=30,
                          timeout=300, log_path=inv.folder / f"reproduce-{attempt}.ndjson")
        inv.kane = _brief(result)
        inv.kane["attempt"] = attempt
        inv.kane.update(evidence.extract_shots(result.session_dir,
                                               inv.folder / f"shots-reproduce-{attempt}"))
        inv.kane["shots_dir"] = f"shots-reproduce-{attempt}"
        inv.attempts.append({"objective": inv.plan["objective"], "kane": inv.kane})

        if result.verdict == "error":
            inv.verdict = "inconclusive"
            break
        if result.verdict == "passed":
            inv.verdict = "not_reproduced"
            break

        step("judging")
        inv.judgement = claude.ask_json(JUDGE_PROMPT.format(
            report=report, expected=inv.plan.get("expected"), objective=inv.plan["objective"],
            result=json.dumps(inv.kane, indent=1, default=str)))
        if inv.judgement.get("reproduced") is True:
            inv.verdict = "reproduced"
            claim = (inv.judgement.get("claim_check") or "").strip()
            if claim:
                inv.verdict = check_claim(app, inv, claim, step)
            break
        inv.verdict = "inconclusive"
        if not inv.judgement.get("agent_lost"):
            break
        # Kane got lost: re-plan using Kane's own account of what went wrong, then try again.
        feedback = RETRY_FEEDBACK.format(
            objective=inv.plan["objective"], kane_summary=inv.kane.get("summary") or inv.kane.get("reason"),
            judge_note=inv.judgement.get("explanation", ""))
    step("done")
    return inv


def check_claim(app: App, inv: Investigation, objective: str, step) -> str:
    """Kane double-checks a claim the verdict relies on. Returns the final verdict."""
    step("double-checking")
    result = kane.run(objective, variables=app.variables(), max_steps=15, timeout=180,
                      log_path=inv.folder / "claim-check.ndjson")
    inv.claim = {"objective": objective, **_brief(result)}
    if result.verdict == "passed":
        inv.claim["outcome"] = "confirmed"
        return "reproduced"
    if result.verdict == "failed":
        inv.claim["outcome"] = "not_true"
        return "not_reproduced"  # the user's premise isn't true in the app: not this bug
    inv.claim["outcome"] = "unknown"
    return "inconclusive"


def _brief(result: kane.KaneResult) -> dict:
    failed = result.failed_step
    return {
        "verdict": result.verdict, "exit_code": result.exit_code, "status": result.status,
        "reason": result.reason, "summary": result.summary, "final_state": result.final_state,
        "failed_step": failed.get("remark") if failed else None,
        "steps": [s.get("remark") for s in result.steps if s.get("remark")],
        "errors": result.errors, "session_dir": result.session_dir,
        "test_url": result.test_url, "credits": result.credits, "duration": result.duration,
    }
