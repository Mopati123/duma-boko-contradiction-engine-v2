#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.source_harvester_engine import build_source_harvester_engine


def parse_args():
    parser = argparse.ArgumentParser(description="Build v2 source harvester records.")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Refuse all registry sources without metadata harvesting.",
    )
    mode.add_argument(
        "--harvest",
        action="store_true",
        help="Attempt metadata-only harvesting for real public registry base URLs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "harvest" if args.harvest else "dry-run"
    result = build_source_harvester_engine(mode=selected_mode)
    print("== Source Harvester Engine v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
