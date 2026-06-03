#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.curated_temporal_url_resolution import (
    build_curated_temporal_url_resolution,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 curated temporal URL resolution records."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate curated temporal source slots without URL resolution.",
    )
    mode.add_argument(
        "--resolve",
        action="store_true",
        help="Resolve only URLs already present in the curated temporal source pack.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "resolve" if args.resolve else "dry-run"
    result = build_curated_temporal_url_resolution(mode=selected_mode)
    print("== Curated Temporal URL Resolution v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
