#!/usr/bin/env python3
"""
Inspect EvidenceObject source records without downloading or transcribing.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from evidence.evidence_ingestion import inspect_evidence_sources


def yes_no(value: bool) -> str:
    return "yes" if value else "no"


def main() -> int:
    records = inspect_evidence_sources()

    print("== Evidence source inspection ==")
    for record in records:
        print(f"Evidence ID: {record['evidence_id']}")
        print(f"Title: {record['title']}")
        print(f"URL: {record['url']}")
        print(f"Evidence Status: {record['verification_status']}")
        print(f"Transcript Status: {record['transcript_status']}")
        print(f"Ready For Transcript Ingestion: {yes_no(record['source_ready'])}")
        print(f"Ready For Status Upgrade: {yes_no(record['upgrade_ready'])}")
        print()

    source_ready_count = sum(1 for record in records if record["source_ready"])
    upgrade_ready_count = sum(1 for record in records if record["upgrade_ready"])
    print(f"Total evidence records: {len(records)}")
    print(f"Ready for transcript ingestion: {source_ready_count}")
    print(f"Ready for status upgrade: {upgrade_ready_count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
