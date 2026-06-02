#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.real_transcript_localization import build_real_transcript_localization


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 real transcript and text localization records."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate harvested sources without localizing transcript or text.",
    )
    mode.add_argument(
        "--localize",
        action="store_true",
        help="Attempt real transcript/caption or HTML body-text localization.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "localize" if args.localize else "dry-run"
    result = build_real_transcript_localization(mode=selected_mode)
    print("== Real Transcript Localization v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
