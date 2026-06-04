#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.temporal_source_harvester import build_temporal_source_harvester


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 temporal source harvester records."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate resolved temporal URLs without network harvesting.",
    )
    mode.add_argument(
        "--harvest",
        action="store_true",
        help="Fetch resolved temporal URLs and harvest content metadata.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "harvest" if args.harvest else "dry-run"
    result = build_temporal_source_harvester(mode=selected_mode)
    print("== Temporal Source Harvester v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
