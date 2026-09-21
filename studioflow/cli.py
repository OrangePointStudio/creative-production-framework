import argparse
import json
from .core import WorkflowError, doctor, export_selection, initialize, run_demo, summarize_costs, verify


def main(argv=None):
    parser = argparse.ArgumentParser(description="Private-workspace creative production skeleton")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("doctor")
    init = sub.add_parser("init")
    init.add_argument("workspace")
    init.add_argument("--lane", choices=["cloud", "hybrid", "local"], default="local")
    for command in ("demo", "verify", "replay", "export", "costs"):
        item = sub.add_parser(command)
        item.add_argument("workspace")
        if command != "costs":
            item.add_argument("--run", required=True)
        if command == "replay":
            item.add_argument("--new-run", required=True)
        if command == "export":
            item.add_argument("--output", required=True)
            item.add_argument("--delivery", action="store_true")
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            result = doctor()
        elif args.command == "init":
            result = initialize(args.workspace, args.lane)
        elif args.command == "demo":
            result = run_demo(args.workspace, args.run)
        elif args.command == "replay":
            result = run_demo(args.workspace, args.new_run, args.run)
        elif args.command == "verify":
            verify(args.workspace, args.run)
            result = {"status": "verified", "run_id": args.run, "human_acceptance": "not inferred"}
        elif args.command == "export":
            result = export_selection(args.workspace, args.run, args.output, args.delivery)
        else:
            result = summarize_costs(args.workspace)
    except (WorkflowError, OSError) as exc:
        # OS errors may contain account paths. Do not dump a traceback or raw provider payload.
        message = str(exc) if isinstance(exc, WorkflowError) else "Local filesystem operation failed. Check access and available space."
        print(json.dumps({"status": "blocked", "reason": message}))
        return 2
    print(json.dumps(result, indent=2, sort_keys=True))
    return 0
