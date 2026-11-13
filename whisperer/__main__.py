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
    args = parser.parse_args(argv)

    result = investigate(App.load(args.app), args.report, args.screenshot,
                         on_update=lambda i: print(f"[whisperer] {i.status}", flush=True))
    print(json.dumps({"verdict": result.verdict, "plan": result.plan,
                      "kane": result.kane, "judgement": result.judgement}, indent=2, default=str))
    print(f"[whisperer] saved to {result.folder / 'investigation.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
