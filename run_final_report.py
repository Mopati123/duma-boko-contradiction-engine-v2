#!/usr/bin/env python3
"""
run_final_report.py - Generates the final governance report from v3 cases.
"""

from pathlib import Path

from evidence.evidence_schema import load_json
from evidence.final_report_generator import FinalReportGenerator


def main():
    divergence_cases_path = Path("outputs/cases/divergence_cases.json")
    if not divergence_cases_path.exists():
        raise FileNotFoundError(
            f"Missing generated divergence cases: {divergence_cases_path}"
        )

    data = load_json(str(divergence_cases_path))
    cases = data.get("cases", [])
    if not cases:
        raise ValueError("No divergence cases available for final report generation")

    generator = FinalReportGenerator(Path("outputs/reports"))
    report_path = generator.generate(cases, "DUMA_BOKO_FINAL_FORENSIC_REPORT.docx")
    print(f"Final Forensic Report Generated: {report_path}")


if __name__ == "__main__":
    main()
