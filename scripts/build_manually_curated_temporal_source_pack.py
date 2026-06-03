#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.manually_curated_temporal_source_pack import (
    build_manually_curated_temporal_source_pack,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 manually curated temporal source pack records."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate the curated temporal source pack without emitting validated sources.",
    )
    mode.add_argument(
        "--build-pack",
        action="store_true",
        help="Emit validated manually curated temporal source pack records.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "build-pack" if args.build_pack else "dry-run"
    result = build_manually_curated_temporal_source_pack(mode=selected_mode)
    print("== Manually Curated Temporal Source Pack v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
