#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.apply_verified_registry_updates import build_apply_verified_registry_updates


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 verified registry update application records."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Preview verified registry updates without modifying the registry.",
    )
    mode.add_argument(
        "--apply",
        action="store_true",
        help="Apply verified registry update candidates to the tracked registry input.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "apply" if args.apply else "dry-run"
    result = build_apply_verified_registry_updates(mode=selected_mode)
    print("== Apply Verified Registry Updates v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
