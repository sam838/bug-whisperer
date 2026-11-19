"""The proof a judge can check fast, gathered only from real records.

- `run_experiments()` runs the pre-registered experiments in docs/proof/experiments.json (written
  and committed before any of them ran) and saves each result in docs/proof/experiments/<id>/.
- `collect()` reads every real record: the experiments, the case studies in docs/evidence/, the
  saved regression tests and the Stop hook's revisits (runs/guard-*). It writes
  docs/proof/results.json (what the /verified page shows) and docs/proof/RESULTS.md.

Nothing here judges anything: every verdict is the one Kane CLI and Bug Whisperer recorded.
"""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from .detective import ROOT, RUNS, App, Investigation, investigate

PROOF = ROOT / "docs" / "proof"
EVIDENCE = ROOT / "docs" / "evidence"
REPO = "https://github.com/sam838/bug-whisperer/blob/main"
VERDICT_WORDS = {"reproduced": "Confirmed", "not_reproduced": "Open: not reproduced",
                 "needs_info": "Open: asked the user", "inconclusive": "Unsolved"}


def _kane_runs(inv: dict) -> list[dict]:
    """Every Kane run a case made: its attempts at the scene, the claim double-check, and each
    repair's re-check and sealed question."""
    runs = [a.get("kane") or {} for a in inv.get("attempts") or []]
    if inv.get("claim"):
        runs.append(inv["claim"])
    for attempt in (inv.get("fix") or {}).get("attempts") or []:
        runs.append(attempt.get("kane") or {})
        runs.append(attempt.get("sealed") or {})
    return [r for r in runs if r]


def _credits(runs: list[dict]) -> float:
    return round(sum(r.get("credits") or 0 for r in runs), 1)


# ── running the experiments ─────────────────────────────────────────────────────────────────

def run_experiments(only: list[str] | None = None, say=print) -> None:
    plan = json.loads((PROOF / "experiments.json").read_text(encoding="utf-8"))
    for exp in plan["experiments"]:
        if only and exp["id"] not in only:
            continue
        say(f"[proof] {exp['id']}: running…")
        started = time.time()
        inv = investigate(App.load(ROOT / exp["app_file"]), exp["report"],
                          on_update=lambda i: say(f"[proof]   {i.status}"))
        inv.note = f"Proof experiment {exp['id']} (pre-registered in docs/proof/experiments.json)"
        inv.save()
        out = PROOF / "experiments" / exp["id"]
        if out.exists():
            shutil.rmtree(out)
        shutil.copytree(inv.folder, out, ignore=shutil.ignore_patterns("live.*", "*.tmp"))
        (out / "run.json").write_text(json.dumps({
            "id": exp["id"], "case_id": inv.id, "ran_at": time.strftime("%Y-%m-%d %H:%M"),
            "seconds": round(time.time() - started), "verdict": inv.verdict}, indent=2), encoding="utf-8")
        say(f"[proof] {exp['id']}: {inv.verdict} (expected {' or '.join(exp['expected'])})")


# ── collecting every real record ────────────────────────────────────────────────────────────

def _experiments() -> list[dict]:
    plan = json.loads((PROOF / "experiments.json").read_text(encoding="utf-8"))
    rows = []
    for exp in plan["experiments"]:
        folder = PROOF / "experiments" / exp["id"]
        row = {**{k: exp[k] for k in ("id", "app_file", "report", "expected", "why")}, "ran": False}
        if (folder / "investigation.json").exists():
            inv = json.loads((folder / "investigation.json").read_text(encoding="utf-8"))
            run = json.loads((folder / "run.json").read_text(encoding="utf-8")) if (folder / "run.json").exists() else {}
            runs = _kane_runs(inv)
            row.update(ran=True, verdict=inv.get("verdict"), as_expected=inv.get("verdict") in exp["expected"],
                       app=inv.get("app"), kane_runs=len(runs), credits=_credits(runs), seconds=run.get("seconds"),
                       ran_at=run.get("ran_at"), explanation=(inv.get("judgement") or {}).get("explanation")
                       or ("Asked the user: " + inv["plan"]["question"] if (inv.get("plan") or {}).get("question") else "")
                       or ("Kane: " + " ".join((inv.get("kane") or {}).get("summary", "").splitlines())
                           if (inv.get("kane") or {}).get("summary") else ""),
                       kane_said=(inv.get("kane") or {}).get("summary") or "",
                       folder=f"docs/proof/experiments/{exp['id']}")
        rows.append(row)
    return rows


def _evidence() -> list[dict]:
    rows = []
    for folder in sorted(p for p in EVIDENCE.iterdir() if p.is_dir()):
        readme = folder / "README.md"
        title = readme.read_text(encoding="utf-8").splitlines()[0].lstrip("# ").strip() if readme.exists() else folder.name
        row = {"id": folder.name, "title": title, "folder": f"docs/evidence/{folder.name}"}
        if (folder / "investigation.json").exists():
            inv = json.loads((folder / "investigation.json").read_text(encoding="utf-8"))
            runs = _kane_runs(inv)
            row.update(app=inv.get("app"), verdict=inv.get("verdict"),
                       fixed=(inv.get("fix") or {}).get("verdict") == "fixed",
                       kane_runs=len(runs), credits=_credits(runs))
        rows.append(row)
    return rows


def _revisits() -> dict:
    reports = sorted(RUNS.glob("guard-*/report.json"))
    if reports:  # keep a copy of every revisit report in the repo, so anyone can check the counts
        keep = PROOF / "revisits"
        keep.mkdir(parents=True, exist_ok=True)
        for path in reports:
            shutil.copyfile(path, keep / f"{path.parent.name}.json")
    else:  # a fresh checkout (or the live server): count the copies kept in the repo
        reports = sorted((PROOF / "revisits").glob("guard-*.json"))
    total = holds = reopened = unknown = 0
    for path in reports:
        for r in json.loads(path.read_text(encoding="utf-8")).get("results", []):
            if r.get("app") == SELF_APP:
                continue
            total += 1
            holds += r.get("verdict") == "holds"
            reopened += r.get("verdict") == "reopened"
            unknown += r.get("verdict") == "unknown"
    def name(path):  # guard-20261113-135655 -> 2026-11-13 13:56
        stamp = (path.parent.name if path.name == "report.json" else path.stem).removeprefix("guard-")
        return f"{stamp[:4]}-{stamp[4:6]}-{stamp[6:8]} {stamp[9:11]}:{stamp[11:13]}"
    first = name(reports[0]) if reports else None
    last = name(reports[-1]) if reports else None
    return {"sessions": len(reports), "replays": total, "holds": holds, "reopened": reopened,
            "unknown": unknown, "first": first, "last": last}


def _regression_tests() -> list[dict]:
    path = ROOT / ".testmuai" / "closed-cases.json"
    cases = json.loads(path.read_text(encoding="utf-8")).get("cases", []) if path.exists() else []
    return [{"title": c["title"], "test": f".testmuai/tests/{c['test']}_test.md", "closed": c.get("closed")}
            for c in cases if not c.get("self_check")]


SELF_APP = "Bug Whisperer (itself)"


def _self_checks() -> dict:
    """Kane checking Bug Whisperer's own pages: the saved checks and their latest replay."""
    path = ROOT / ".testmuai" / "closed-cases.json"
    checks = [c for c in (json.loads(path.read_text(encoding="utf-8")).get("cases", []) if path.exists() else [])
              if c.get("self_check")]
    latest, when, caught = {}, None, []
    notes_file = PROOF / "selfcheck-notes.json"
    notes = json.loads(notes_file.read_text(encoding="utf-8")) if notes_file.exists() else {}
    stamp = lambda s: f"{s[:4]}-{s[4:6]}-{s[6:8]} {s[9:11]}:{s[11:13]}"
    for report in sorted((PROOF / "revisits").glob("guard-*.json")):
        data = json.loads(report.read_text(encoding="utf-8"))
        rows = [r for r in data.get("results", []) if r.get("app") == SELF_APP]
        checked = [r for r in rows if r.get("verdict") != "unknown"]  # "unknown": Kane couldn't check
        if checked:
            latest.update({r["case_id"]: r for r in checked})
            when = report.stem.removeprefix("guard-")
        for r in rows:  # every time a check failed: proof the checks can fail
            if r.get("verdict") == "reopened":
                said = (r.get("fresh") or {}).get("summary") or (r.get("replay") or {}).get("summary") or ""
                caught.append({"when": stamp(report.stem.removeprefix("guard-")), "id": r["case_id"],
                               "title": r.get("title", ""), "kane_said": said, "note": notes.get(report.stem, "")})
    rows = [{"id": c["case_id"], "title": c["title"], "objective": c["objective"],
             "test": f".testmuai/tests/{c['test']}_test.md", "verdict": (latest.get(c["case_id"]) or {}).get("verdict")}
            for c in checks]
    return {"checks": rows, "last_run": stamp(when) if when else None,
            "passing": sum(r["verdict"] == "holds" for r in rows), "caught": caught}


def _lineups() -> list[dict]:
    """Lineups kept as evidence in the repo (docs/evidence/*/lineup.json): who broke what."""
    rows = []
    for path in sorted(EVIDENCE.glob("*/lineup.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        culprit = next((s for s in data["suspects"] if s["status"] == "guilty"), None)
        rows.append({"id": data["id"], "folder": f"docs/evidence/{path.parent.name}", "title": data["title"],
                     "verdict": data["verdict"], "suspects": len(data["suspects"]),
                     "questionings": data["questionings"], "fresh_runs": data.get("fresh_runs", 0),
                     "culprit": {k: culprit[k] for k in ("short", "subject", "date")} if culprit else None})
    return rows


def collect() -> dict:
    """Gather everything, write docs/proof/results.json and RESULTS.md, and return it."""
    experiments, evidence = _experiments(), _evidence()
    revisits, tests, lineups = _revisits(), _regression_tests(), _lineups()
    ran = [e for e in experiments if e["ran"]]
    results = {
        "generated": time.strftime("%Y-%m-%d %H:%M"),
        "repo": REPO,
        "experiments": experiments,
        "evidence": evidence,
        "revisits": revisits,
        "regression_tests": tests,
        "self_checks": _self_checks(),
        "lineups": lineups,
        "totals": {
            "experiments_run": len(ran),
            "experiments_as_expected": sum(e["as_expected"] for e in ran),
            "kane_runs": (sum(e.get("kane_runs", 0) for e in ran + evidence) + revisits["replays"]
                          + sum(x["questionings"] for x in lineups)),
            "credits": round(sum(e.get("credits", 0) for e in ran + evidence), 1),
        },
    }
    PROOF.mkdir(parents=True, exist_ok=True)
    (PROOF / "results.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    (PROOF / "RESULTS.md").write_text(markdown(results), encoding="utf-8")
    return results


def markdown(r: dict) -> str:
    t = r["totals"]
    lines = [
        "# Bug Whisperer: verified results",
        "",
        f"*Generated {r['generated']} by `python -m whisperer proof` from the real records in this repo. "
        "Every verdict below is the one Kane CLI and Bug Whisperer recorded; nothing is typed in by hand.*",
        "",
        f"- **{t['experiments_as_expected']} of {t['experiments_run']}** pre-registered experiments came out as expected "
        "([the expectations were committed before any ran](experiments.json)).",
        f"- **{len(r['evidence'])}** case studies with full evidence, **{len(r['regression_tests'])}** bugs fixed and kept as Kane regression tests.",
        f"- **{r['revisits']['replays']}** automatic Kane revisits of closed cases by the Claude Code Stop hook "
        f"({r['revisits']['holds']} held, {r['revisits']['reopened']} reopened, {r['revisits']['unknown']} unclear).",
        f"- About **{t['kane_runs']}** Kane CLI runs in total.",
        "",
        "## Pre-registered experiments",
        "",
        "Does Bug Whisperer refuse to invent bugs, ignore instructions hidden in a report, and ask instead of guessing?",
        "",
        "| Experiment | Expected | Bug Whisperer said | As expected? | Kane runs |",
        "| --- | --- | --- | --- | --- |",
    ]
    for e in r["experiments"]:
        expected = " or ".join(VERDICT_WORDS.get(x, x) for x in e["expected"])
        if e["ran"]:
            got = VERDICT_WORDS.get(e["verdict"], e["verdict"])
            ok = "✅ yes" if e["as_expected"] else "❌ **no**"
            lines.append(f"| [{e['id']}]({e['folder'].removeprefix('docs/proof/')}) | {expected} | {got} | {ok} | {e['kane_runs']} |")
        else:
            lines.append(f"| {e['id']} | {expected} | not run yet | | |")
    lines += ["", "What each one tested, and what was said:", ""]
    for e in r["experiments"]:
        lines.append(f"- **{e['id']}**: {e['why']}")
        lines.append(f"  - Report: *“{e['report']}”*")
        if e.get("explanation"):
            lines.append(f"  - Bug Whisperer: {e['explanation']}")
    lines += ["", "## Case studies (full evidence)", "", "| Case | App | Verdict | Fixed? | Kane runs |", "| --- | --- | --- | --- | --- |"]
    for c in r["evidence"]:
        verdict = VERDICT_WORDS.get(c.get("verdict"), "see the write-up")
        fixed = "✅ Kane saw the fix" if c.get("fixed") else "–"
        lines.append(f"| [{c['title']}](../evidence/{c['id']}/) | {c.get('app', 'Clinic Records')} | {verdict} | {fixed} | {c.get('kane_runs', '–')} |")
    sc = r.get("self_checks") or {}
    if sc.get("checks"):
        lines += ["", "## Kane checks Bug Whisperer itself", "",
                  f"Bug Whisperer's own pages are saved Kane tests too, replayed with no self-healing whenever its code "
                  f"changes. Last run {sc['last_run']}: **{sc['passing']} of {len(sc['checks'])} passing**.", ""]
        for c in sc["checks"]:
            mark = {"holds": "✅", None: "–"}.get(c["verdict"], "❌")
            lines.append(f"- {mark} {c['title']}: [`{c['test'].split('/')[-1]}`](../../{c['test']})")
        for x in sc.get("caught", []):
            lines.append(f"- 🔎 {x['when']}: *{x['title']}* failed. Kane: “{x['kane_said']}”"
                         + (f" *({x['note']})*" if x.get("note") else ""))
    if r.get("lineups"):
        lines += ["", "## The Lineup: who broke it?", "",
                  "Kane names the commit that broke a closed case: each version he questions is checked out, "
                  "started, and tested in a real browser, halving the suspects each time.", ""]
        for x in r["lineups"]:
            found = (f"named `{x['culprit']['short']}` “{x['culprit']['subject']}” ({x['culprit']['date']})"
                     if x["culprit"] else f"accused no one ({x['verdict']})")
            lines.append(f"- [{x['title']}](../evidence/{x['folder'].split('/')[-1]}/): {x['suspects']} suspects, "
                         f"{x['questionings']} questioned ({x['fresh_runs']} fresh Kane runs), {found}.")
    lines += ["", "## Kept on file as Kane regression tests", ""]
    for x in r["regression_tests"]:
        lines.append(f"- {x['title']}: [`{x['test']}`](../../{x['test']}) (closed {x['closed']})")
    v = r["revisits"]
    lines += ["", "## The Stop hook's revisits", "",
              f"Between {v['first']} and {v['last']}, the Claude Code Stop hook replayed the closed cases "
              f"**{v['replays']}** times in **{v['sessions']}** sessions: {v['holds']} still closed, "
              f"{v['reopened']} reopened, {v['unknown']} unclear ([every report](revisits/)). The reopening that blocked a session until it was "
              "fixed is written up in [evidence 004](../evidence/004-hook-reopened-case/).", ""]
    return "\n".join(lines)
