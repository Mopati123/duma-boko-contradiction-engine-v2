#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.web_source_discovery_engine import build_web_source_discovery_engine


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 web source discovery records."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Refuse unresolved validated seed URLs without web access.",
    )
    mode.add_argument(
        "--search-web",
        action="store_true",
        help="Attempt public source discovery without extracting quotes or timestamps.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "search-web" if args.search_web else "dry-run"
    result = build_web_source_discovery_engine(mode=selected_mode)
    print("== Web Source Discovery Engine v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
