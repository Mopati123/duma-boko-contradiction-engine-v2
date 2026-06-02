#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.transcript_localization_engine import (
    build_transcript_localization_engine,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 transcript localization records."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate upstream harvested sources without transcript localization.",
    )
    mode.add_argument(
        "--localize",
        action="store_true",
        help="Attempt transcript localization for harvested audio/video sources.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "localize" if args.localize else "dry-run"
    result = build_transcript_localization_engine(mode=selected_mode)
    print("== Transcript Localization Engine v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
