#!/usr/bin/env python3

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.final_word_report_preview import build_final_word_report_preview


def parse_args():
    parser = argparse.ArgumentParser(
        description="Build draft DOCX progress preview report for human review."
    )
    parser.add_argument(
        "--build-preview",
        action="store_true",
        help="Build the draft DOCX preview. This is the default action.",
    )
    return parser.parse_args()


def main() -> int:
    parse_args()
    result = build_final_word_report_preview()
    print("== Final Word Report Preview summary ==")
    for key, value in result["summary"].items():
        print(f"{key}: {value}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
