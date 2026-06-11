#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.manual_after_temporal_claim_normalization import (
    build_manual_after_temporal_claim_normalization,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build temporal claim candidates from manual AFTER snapshot claims."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate manual AFTER snapshot claims without emitting temporal claims.",
    )
    mode.add_argument(
        "--normalize",
        action="store_true",
        help="Emit temporal claim candidates from manual AFTER snapshot claims.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "normalize" if args.normalize else "dry-run"
    result = build_manual_after_temporal_claim_normalization(mode=selected_mode)
    print("== Manual AFTER Temporal Claim Normalization summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
