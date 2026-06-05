#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.after_source_candidate_intake import build_after_source_candidate_intake


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 AFTER-source candidate intake validation."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate AFTER-source candidate intake template shape only.",
    )
    mode.add_argument(
        "--validate-intake",
        action="store_true",
        help="Validate supplied AFTER-source candidate URLs.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "validate-intake" if args.validate_intake else "dry-run"
    result = build_after_source_candidate_intake(mode=selected_mode)
    print("== AFTER-Source Candidate Intake v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
