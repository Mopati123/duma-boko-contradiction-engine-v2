#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.manual_after_snapshot_claim_extraction import (
    build_manual_after_snapshot_claim_extraction,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 manual AFTER snapshot claim candidates."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate manual AFTER snapshot evidence packets without extracting claims.",
    )
    mode.add_argument(
        "--extract-claims",
        action="store_true",
        help="Extract conservative claims from manual AFTER snapshot evidence packets.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "extract-claims" if args.extract_claims else "dry-run"
    result = build_manual_after_snapshot_claim_extraction(mode=selected_mode)
    print("== Manual AFTER Snapshot Claim Extraction v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
