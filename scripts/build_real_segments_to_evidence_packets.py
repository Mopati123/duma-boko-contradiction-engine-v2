#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.real_segments_to_evidence_packets import (
    build_real_segments_to_evidence_packets,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build v2 real evidence packets from localized transcript segments."
    )
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate localized segments and owner lookup without packet generation.",
    )
    mode.add_argument(
        "--from-segments",
        action="store_true",
        help="Create real evidence packets from localized transcript segments.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    selected_mode = "from-segments" if args.from_segments else "dry-run"
    result = build_real_segments_to_evidence_packets(mode=selected_mode)
    print("== Real Segments To Evidence Packets v2 summary ==")
    print(f"Mode: {selected_mode}")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
