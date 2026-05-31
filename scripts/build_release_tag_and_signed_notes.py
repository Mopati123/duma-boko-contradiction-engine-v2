#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.release_tag_and_signed_notes import build_release_tag_and_signed_notes


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build release tag and signed notes candidate records."
    )
    parser.add_argument("--dry-run", action="store_true", help="Dry-run only.")
    return parser.parse_args()


def main() -> int:
    parse_args()

    result = build_release_tag_and_signed_notes()
    summary = result["summary"]

    print("== Release Tag and Signed Notes Engine v1 summary ==")
    print("Mode: dry-run")

    for key, value in summary.items():
        print(f"{key}: {value}")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())