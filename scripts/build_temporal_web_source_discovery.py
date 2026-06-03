#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.temporal_web_source_discovery import (
    build_temporal_web_source_discovery,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 temporal web source discovery."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate temporal discovery seeds without accessing the internet.",
    )
    mode.add_argument(
        "--discover-web",
        action="store_true",
        help="Discover public source candidates from temporal seed search queries.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "discover-web" if args.discover_web else "dry-run"
    result = build_temporal_web_source_discovery(mode=selected_mode)
    print("== Temporal Web Source Discovery v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
