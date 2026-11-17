"""Command line: `bug-whisperer` when installed, `python -m whisperer` from the repository.

  bug-whisperer init --sample     a project folder with the sample clinic app
  bug-whisperer doctor            check the setup (spends no Kane credits)
  bug-whisperer up                the website
  bug-whisperer investigate apps/clinic.json "cant book!!!" [--screenshot x.png]
"""

import argparse
import json
import sys

from .detective import App, investigate


def main(argv=None) -> int:
    for stream in (sys.stdout, sys.stderr):  # a console that can't show ✅ shows ? instead of failing
        try:
            stream.reconfigure(errors="replace")
        except (AttributeError, ValueError):
            pass
    parser = argparse.ArgumentParser(prog="bug-whisperer",
                                     description="Turn messy bug reports into Kane CLI reproductions and proven fixes.")
    sub = parser.add_subparsers(dest="cmd", required=True)
    it = sub.add_parser("init", help="Set up this folder: the sample app (--sample) or your own app")
    it.add_argument("--sample", action="store_true", help="Copy the sample clinic app, bugs included")
    it.add_argument("--name", help="Your app's name, e.g. 'My Shop'")
    it.add_argument("--url", help="Where it runs, e.g. http://localhost:3000")
    it.add_argument("--about", default="", help="One sentence on what the app is for (helps Claude plan)")
    it.add_argument("--login-path", default="", help="The login page's path, e.g. /login")
    it.add_argument("--account", action="append", default=[], metavar="LABEL=EMAIL",
                    help="A test account (repeatable); its password is asked for and kept in apps/secrets/")
    it.add_argument("--code", help="Your app's code folder: Bug Whisperer may then repair bugs in it")
    it.add_argument("--start", help="The command that starts your app, run in --code")
    it.add_argument("--reset", help="The command that resets its test data, run in --code")
    rp = sub.add_parser("report", help="Send Kane to investigate a bug report, and follow it live")
    rp.add_argument("text", nargs="?", default="", help="The report, as the user wrote it")
    rp.add_argument("--app", help="Which connected app (needed when there are several)")
    rp.add_argument("--file", action="append", default=[], metavar="PATH",
                    help="Test results or screenshots (repeatable): one case per real problem")
    rp.add_argument("--screenshot", help="The user's screenshot, for a single report")
    choice = rp.add_mutually_exclusive_group()
    choice.add_argument("--repair", dest="repair", action="store_true", default=None,
                        help="If Kane confirms the bug, repair it without asking")
    choice.add_argument("--no-repair", dest="repair", action="store_false", help="Don't offer a repair")
    rr = sub.add_parser("repair", help="Repair a confirmed case: Claude fixes it, Kane proves it")
    rr.add_argument("case", help="The case id (see: bug-whisperer cases)")
    sub.add_parser("cases", help="The cases on file, newest first")
    dr = sub.add_parser("doctor", help="Check Kane CLI, Claude Code, Chrome and your apps (spends no credits)")
    dr.add_argument("--port", type=int, default=8000)
    upp = sub.add_parser("up", help="Start the website")
    upp.add_argument("--port", type=int, default=8000)
    upp.add_argument("--host", default="127.0.0.1")
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

    if args.cmd in ("report", "repair", "cases"):
        from . import terminal
        if args.cmd == "cases":
            rows = terminal.list_cases()
            print("\n".join(rows) if rows else "No cases yet. Try: bug-whisperer report \"cant book!!!\"")
            return 0
        if args.cmd == "repair":
            inv = terminal.load_case(args.case)
            if inv.verdict != "reproduced":
                print("Only a confirmed bug can be repaired: Kane has to see it first.")
                return 1
            app = App.load(terminal.ROOT / inv.app_file)
            if not app.code_dir:
                print(f"{app.name} has no code connected, so Bug Whisperer can reproduce its bugs but not repair them.")
                return 1
            return 0 if terminal.repair(inv, app)["verdict"] == "fixed" else 1
        cases = terminal.report(args.text, terminal.choose_app(args.app), args.file, args.screenshot, args.repair)
        return 0 if all(c.verdict in ("reproduced", "not_reproduced", "needs_info") for c in cases) else 1

    if args.cmd in ("init", "doctor", "up"):
        from . import workspace
        if args.cmd == "up":
            workspace.up(args.port, args.host)
            return 0
        if args.cmd == "doctor":
            checks = workspace.doctor(args.port)
            for mark, found, fix in checks:
                print(f"{mark} {found}" + (f"\n     → {fix}" if fix else ""))
            blocked = any(mark == "❌" for mark, _, _ in checks)
            print("\nSomething above needs fixing first." if blocked else
                  '\nReady. In the terminal: bug-whisperer report "cant book!!! it just saved it"'
                  "\n       On the website:  bug-whisperer up")
            return 1 if blocked else 0
        if args.sample:
            for line in workspace.init_sample():
                print(f"  {line}")
        elif args.name and args.url:
            try:
                path = workspace.init_app(args.name, args.url, about=args.about, code=args.code, start=args.start,
                                          reset=args.reset, login_path=args.login_path, accounts=args.account)
            except ValueError as e:
                parser.error(str(e))
            print(f"  {path.relative_to(workspace.ROOT)}: {args.name} at {args.url}"
                  + (f", code in {args.code}" if args.code else " (link only: reproduce and report)"))
        else:
            parser.error("init needs --sample, or --name and --url for your own app")
        print('\nNext: bug-whisperer doctor, then bug-whisperer report "<the bug report>"'
              " (or bug-whisperer up for the website)")
        return 0

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
