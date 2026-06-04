#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.populate_verified_temporal_url_intake import (
    build_populate_verified_temporal_url_intake,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 populated verified temporal URL intake records."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview metadata-pack population without modifying the intake template.",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Populate the verified temporal URL intake template from the metadata pack.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "apply" if args.apply else "dry-run"
    result = build_populate_verified_temporal_url_intake(mode=selected_mode)
    print("== Populate Verified Temporal URL Intake v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
