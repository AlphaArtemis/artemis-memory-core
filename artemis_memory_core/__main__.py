"""Local operator CLI. Document contents are always returned as JSON data."""
import argparse
import json
import sys

from .core import Engine, MemoryError


def main(argv=None):
    parser = argparse.ArgumentParser(description="Artemis Memory Core — Community Edition")
    parser.add_argument("--version", action="version", version="0.1.0-alpha.1")
    commands = parser.add_subparsers(dest="command", required=True)
    for name in ("init", "status", "preview", "import", "search", "fetch", "revoke", "demo"):
        sub = commands.add_parser(name)
        sub.add_argument("--state", required=True, help="Explicit absolute local state directory")
        if name in ("preview", "import"):
            sub.add_argument("filename", help="JSON filename already placed in state/inbox")
        if name == "import":
            sub.add_argument("--approval", required=True, help="Exact SHA-256 returned by preview")
        if name == "search":
            sub.add_argument("query")
            sub.add_argument("--limit", type=int, default=5)
            sub.add_argument("--project")
            sub.add_argument("--cursor")
        if name in ("fetch", "revoke"):
            sub.add_argument("source_id")
        if name == "fetch":
            sub.add_argument("--start", type=int, default=0)
            sub.add_argument("--limit", type=int, default=6000)
    args = parser.parse_args(argv)
    try:
        if args.command == "demo":
            from demo.prepare import prepare_demo
            result = prepare_demo(args.state)
        else:
            engine = Engine(args.state)
            if args.command == "init":
                result = engine.initialize()
            elif args.command == "status":
                result = engine.status()
            elif args.command == "preview":
                result = engine.prepare_import(args.filename)
            elif args.command == "import":
                result = engine.apply_import(args.filename, args.approval)
            elif args.command == "search":
                result = engine.search(args.query, limit=args.limit, project=args.project, cursor=args.cursor)
            elif args.command == "fetch":
                result = engine.fetch(args.source_id, start=args.start, limit=args.limit)
            else:
                result = engine.revoke(args.source_id)
        print(json.dumps(result, ensure_ascii=False, allow_nan=False, indent=2))
        return 0
    except MemoryError as error:
        # Do not emit partial results, file contents, paths or a traceback.
        print(json.dumps({"status": "BLOCKED", "error": error.code}), file=sys.stderr)
        return 2
    except (OSError, ValueError, KeyError, TypeError):
        print(json.dumps({"status": "BLOCKED", "error": "local_operation_failed"}), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
