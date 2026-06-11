#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.manual_before_snapshot_to_harvested_source import (
    build_manual_before_snapshot_to_harvested_source,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build no-fetch harvested source records from manual BEFORE snapshots."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate manual BEFORE snapshot artifacts without emitting harvested sources.",
    )
    mode.add_argument(
        "--from-snapshots",
        action="store_true",
        help="Emit harvested temporal source records from validated manual BEFORE snapshots.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "from-snapshots" if args.from_snapshots else "dry-run"
    result = build_manual_before_snapshot_to_harvested_source(mode=selected_mode)
    print("== Manual BEFORE Snapshot To Harvested Source summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
