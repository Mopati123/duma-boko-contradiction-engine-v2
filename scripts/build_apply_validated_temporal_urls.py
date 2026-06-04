#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.apply_validated_temporal_urls import (
    build_apply_validated_temporal_urls,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 apply validated temporal URL records."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview applying validated temporal URLs without modifying the source pack.",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Apply validated temporal URLs to the curated temporal source pack.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "apply" if args.apply else "dry-run"
    result = build_apply_validated_temporal_urls(mode=selected_mode)
    print("== Apply Validated Temporal URLs v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
