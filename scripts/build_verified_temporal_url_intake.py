#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.verified_temporal_url_intake import (
    build_verified_temporal_url_intake,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 verified temporal URL intake records."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate temporal URL intake template shape without URL checks.",
    )
    mode.add_argument(
        "--validate-intake",
        action="store_true",
        help="Validate only URLs supplied in the temporal URL intake template.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "validate-intake" if args.validate_intake else "dry-run"
    result = build_verified_temporal_url_intake(mode=selected_mode)
    print("== Verified Temporal URL Intake v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
