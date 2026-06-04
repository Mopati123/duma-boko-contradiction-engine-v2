#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.temporal_claim_normalization import build_temporal_claim_normalization


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 normalized temporal claim identities."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate temporal claims without normalization.",
    )
    mode.add_argument(
        "--normalize",
        action="store_true",
        help="Normalize temporal claims into canonical identities.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "normalize" if args.normalize else "dry-run"
    result = build_temporal_claim_normalization(mode=selected_mode)
    print("== Temporal Claim Normalization v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
