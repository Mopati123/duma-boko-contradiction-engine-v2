#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.real_claim_normalization import build_real_claim_normalization


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 canonical normalized real claims."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate real extracted claims without normalization.",
    )
    mode.add_argument(
        "--normalize",
        action="store_true",
        help="Normalize real extracted claims into canonical semantic objects.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "normalize" if args.normalize else "dry-run"
    result = build_real_claim_normalization(mode=selected_mode)
    print("== Real Claim Normalization v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
