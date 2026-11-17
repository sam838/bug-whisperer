"""Command line: python -m whisperer investigate apps/clinic.json "cant book!!!" [--screenshot x.png]"""

import argparse
import json
import sys

from .detective import App, investigate


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="whisperer")
    sub = parser.add_subparsers(dest="cmd", required=True)
    inv = sub.add_parser("investigate", help="Reproduce a messy bug report with Kane CLI")
    inv.add_argument("app", help="Path to an app JSON file, e.g. apps/clinic.json")
    inv.add_argument("report", help="The user's bug report, as they wrote it")
    inv.add_argument("--screenshot", help="Path to the user's screenshot")
    fx = sub.add_parser("fix", help="Fix a reproduced bug, then re-check it with Kane CLI")
    fx.add_argument("app", help="Path to the app JSON file (its code_dir is what gets edited)")
    fx.add_argument("run", help="Folder of a reproduced investigation, e.g. runs/20261113-112727")
    gd = sub.add_parser("guard", help="Kane revisits every closed case: is any old bug back?")
    gd.add_argument("--app", help="Only this app's cases, e.g. apps/clinic.json")
    sub.add_parser("hook", help="Claude Code Stop hook (reads the hook JSON on stdin)")
    ex = sub.add_parser("experiments", help="Run the pre-registered proof experiments (real Kane runs)")
    ex.add_argument("ids", nargs="*", help="Only these experiment ids")
    sub.add_parser("proof", help="Gather the real records into docs/proof/results.json and RESULTS.md")
    sc = sub.add_parser("selfcheck", help="Kane checks Bug Whisperer's own pages (replays the saved checks)")
    sc.add_argument("--record", action="store_true", help="Run each check once and save it as a Kane test")
    args = parser.parse_args(argv)

    if args.cmd == "hook":
        from .hook import main as hook_main
        return hook_main()

    if args.cmd == "selfcheck":
        from . import selfcheck
        if args.record:
            done = selfcheck.record()
            print(f"[selfcheck] {sum(d['verdict'] == 'passed' for d in done)}/{len(done)} checks recorded")
        report = selfcheck.run()
        for r in report["results"]:
            print(f"  {'✅' if r['verdict'] == 'holds' else '❌'} {r['case_id']}: {r['title']}")
        return 1 if report["reopened"] or report["unknown"] else 0

    if args.cmd in ("experiments", "proof"):
        from .proof import collect, run_experiments
        if args.cmd == "experiments":
            run_experiments(args.ids or None)
        r = collect()
        t = r["totals"]
        print(f"[proof] {t['experiments_as_expected']}/{t['experiments_run']} experiments as expected; "
              f"{t['kane_runs']} Kane runs on record. Written to docs/proof/RESULTS.md")
        return 0

    if args.cmd == "guard":
        from .guard import revisit
        report = revisit(args.app, on_update=lambda m: print(f"[kane] {m}", flush=True))
        marks = {"holds": "✅ still closed", "reopened": "🔁 REOPENED", "unknown": "⚠️ unknown"}
        for r in report["results"]:
            print(f"  {marks[r['verdict']]:16} case {r['case_id']}: {r['title']}")
        print(f"[kane] {len(report['results'])} case(s) revisited, {len(report['reopened'])} reopened")
        return 1 if report["reopened"] else 0

    if args.cmd == "fix":
        from .fixer import fix, load_investigation
        record = fix(App.load(args.app), load_investigation(args.run),
                     on_update=lambda s: print(f"[whisperer] {s}", flush=True))
        print(json.dumps({k: v for k, v in record.items() if k != "attempts"}, indent=2))
        for a in record["attempts"]:
            print(f"--- attempt {a['attempt']}: Kane {a['kane']['verdict']}: {a['kane']['reason']}")
            print("fixer said:", a["fixer_said"].strip()[-600:])
            print(a["patch"][:3000])
        return 0 if record["verdict"] == "fixed" else 1

    result = investigate(App.load(args.app), args.report, args.screenshot,
                         on_update=lambda i: print(f"[whisperer] {i.status}", flush=True))
    print(json.dumps({"verdict": result.verdict, "plan": result.plan,
                      "kane": result.kane, "judgement": result.judgement}, indent=2, default=str))
    print(f"[whisperer] saved to {result.folder / 'investigation.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
