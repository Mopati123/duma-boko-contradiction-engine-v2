#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.manual_before_source_snapshot_intake import (
    build_manual_before_source_snapshot_intake,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build manual BEFORE source snapshot intake artifacts."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate manual BEFORE snapshot template shape and linkage.",
    )
    mode.add_argument(
        "--validate",
        action="store_true",
        help="Validate supplied manual BEFORE source snapshot text.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "validate" if args.validate else "dry-run"
    result = build_manual_before_source_snapshot_intake(mode=selected_mode)
    print("== Manual BEFORE Source Snapshot Intake summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
