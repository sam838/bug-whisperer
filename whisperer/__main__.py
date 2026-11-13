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
    args = parser.parse_args(argv)

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
