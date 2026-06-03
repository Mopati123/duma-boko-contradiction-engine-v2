#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.real_evidence_packets_to_claims import (
    build_real_evidence_packets_to_claims,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 real claim candidates from real evidence packets."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate real evidence packets without extracting claims.",
    )
    mode.add_argument(
        "--extract-claims",
        action="store_true",
        help="Extract conservative real claim candidates from packet text.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "extract-claims" if args.extract_claims else "dry-run"
    result = build_real_evidence_packets_to_claims(mode=selected_mode)
    print("== Real Evidence Packets To Claims v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
