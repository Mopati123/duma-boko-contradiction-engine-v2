#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.evidence_discovery_execution_engine import (
    build_evidence_discovery_execution_engine,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 evidence discovery execution records."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--dry-run", action="store_true", help="Refuse unresolved seed URLs.")
    mode.add_argument("--from-seeds", action="store_true", help="Process tracked seed input.")
    parser.add_argument(
        "--allow-web-search",
        action="store_true",
        help="Allow future local resolver attempts; no URL is invented.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "from-seeds" if args.from_seeds else "dry-run"
    result = build_evidence_discovery_execution_engine(
        mode=selected_mode,
        allow_web_search=args.allow_web_search,
    )
    print("== Evidence Discovery Execution Engine v2 summary ==")
    print(f"Mode: {selected_mode}")
    print(f"Allow web search: {args.allow_web_search}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
