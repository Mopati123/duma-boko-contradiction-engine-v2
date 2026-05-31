#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.release_execution_checklist import build_release_execution_checklist


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build release execution checklist candidate records."
    )
    parser.add_argument("--dry-run", action="store_true", help="Dry-run only.")
    return parser.parse_args()


def main() -> int:
    parse_args()

    result = build_release_execution_checklist()
    summary = result["summary"]

    print("== Release Execution Checklist Engine v1 summary ==")
    print("Mode: dry-run")

    for key, value in summary.items():
        print(f"{key}: {value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
