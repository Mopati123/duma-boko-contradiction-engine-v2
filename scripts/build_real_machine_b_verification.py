#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.real_machine_b_verification import build_real_machine_b_verification


def parse_args():
    parser = argparse.ArgumentParser(
        description="Verify the externally produced real Machine-B proof package."
    )
    parser.add_argument("--dry-run", action="store_true", help="Dry-run only.")
    parser.add_argument(
        "--machine-b-dir",
        default="machine_b_result",
        help="Directory containing extracted Machine-B proof package.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    result = build_real_machine_b_verification(Path(args.machine_b_dir))
    summary = result["summary"]

    print("== Real Machine-B Verification Engine v1 summary ==")
    print("Mode: dry-run")

    for key, value in summary.items():
        print(f"{key}: {value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())