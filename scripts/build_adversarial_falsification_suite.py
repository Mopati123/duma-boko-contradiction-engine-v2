#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.adversarial_falsification_suite import (
    build_adversarial_falsification_suite,
)


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build adversarial falsification suite records."
    )
    parser.add_argument("--dry-run", action="store_true", help="Dry-run only.")
    return parser.parse_args()


def main() -> int:
    parse_args()

    result = build_adversarial_falsification_suite()
    summary = result["summary"]

    print("== Adversarial Falsification Suite v1 summary ==")
    print("Mode: dry-run")

    for key, value in summary.items():
        print(f"{key}: {value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())