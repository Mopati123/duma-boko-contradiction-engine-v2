#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.before_temporal_claim_normalization import (
    build_before_temporal_claim_normalization,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build BEFORE temporal claim candidates from generic extracted temporal claims."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate extracted BEFORE claims without emitting temporal candidates.",
    )
    mode.add_argument(
        "--normalize",
        action="store_true",
        help="Emit BEFORE temporal claim candidates from extracted BEFORE claims.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "normalize" if args.normalize else "dry-run"
    result = build_before_temporal_claim_normalization(mode=selected_mode)
    print("== BEFORE Temporal Claim Normalization summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
