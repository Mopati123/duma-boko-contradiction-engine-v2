#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.temporal_content_localization import build_temporal_content_localization


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 temporal content localization records."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate harvested temporal sources without localization.",
    )
    mode.add_argument(
        "--localize",
        action="store_true",
        help="Localize harvested temporal content into deterministic text segments.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "localize" if args.localize else "dry-run"
    result = build_temporal_content_localization(mode=selected_mode)
    print("== Temporal Content Localization v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
