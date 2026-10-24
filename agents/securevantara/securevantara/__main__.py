"""CLI: private JSON reports; status reflects execution, never absence of bugs."""
import argparse
import json
import http.client
from datetime import datetime, timezone

from .adapter import authorize, run_xalgorix
from .checks import check, deduplicate
from .local_llm import review


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("operation", choices=["check", "review", "xalgorix-info", "xalgorix-review"])
    parser.add_argument("--model", default="gemma4:e4b")
    parser.add_argument("--source")
    parser.add_argument("--scope")
    parser.add_argument("--authorized", action="store_true")
    parser.add_argument("--sandboxed", action="store_true")
    parser.add_argument("--executable", default="xalgorix")
    parser.add_argument("--timeout", type=float, default=300)
    parser.add_argument("--output-limit", type=int, default=65536)
    parser.add_argument("--report", required=True)
    args = parser.parse_args(argv)
    try:
        stream = open(args.report, "x", encoding="utf-8", opener=private_file)
    except OSError as exc:
        parser.exit(2, f"cannot create report: {exc}\n")
    report = dict(schema_version="1.0", operation=args.operation, findings=[], errors=[],
                  started_at=datetime.now(timezone.utc).isoformat(),
                  source=args.source, scope=args.scope, authorized=args.authorized)
    try:
        if args.operation in {"check", "review"}:
            if not args.source or not args.scope:
                raise ValueError("--source and --scope required")
            root = authorize(args.source, args.scope, args.authorized)
            report["findings"], report["errors"] = check(root)
            if args.operation == "review":
                report["local_llm"] = review(root, args.model, min(args.timeout, 300))
                report["findings"] = deduplicate(report["findings"] + report["local_llm"]["findings"])
                if report["local_llm"]["error"]:
                    report["errors"].append(report["local_llm"]["error"])
        else:
            if args.operation == "xalgorix-review" and (not args.source or not args.scope):
                raise ValueError("--source and --scope required")
            report["xalgorix"] = run_xalgorix(
                args.executable,
                args.source if args.operation == "xalgorix-review" else None,
                args.scope, args.authorized, args.sandboxed,
                args.timeout, args.output_limit)
            if report["xalgorix"].get("error"):
                report["errors"].append(report["xalgorix"]["error"])
    except (ValueError, OSError, http.client.HTTPException) as exc:
        report["errors"].append(str(exc))
    status = 2 if report["errors"] else 0
    report["exit_status"] = status
    report["finished_at"] = datetime.now(timezone.utc).isoformat()
    try:
        # Exclusive creation avoids clobbering evidence or following report symlinks.
        with stream:
            json.dump(report, stream, indent=2, ensure_ascii=True)
            stream.write("\n")
    except OSError as exc:
        parser.exit(2, f"cannot create report: {exc}\n")
    return status


def private_file(path, flags):
    import os
    return os.open(path, flags, 0o600)


if __name__ == "__main__":
    raise SystemExit(main())
