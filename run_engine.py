#!/usr/bin/env python3
"""
run_engine.py - Governance Promise-Delivery Divergence Reconstruction Engine.

v3.0: Orchestrates the strategic pivot to divergence reconstruction.
"""

import os
import sys
import argparse
import logging
from pathlib import Path
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("divergence_engine.log"),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger("DivergenceEngine")

# Add current directory to path
sys.path.insert(0, str(Path(__file__).parent))

from analysis.target_search import run_divergence_engine
from evidence.word_exporter import WordExporter

def run_pipeline(args):
    """Run the Governance Divergence Reconstruction pipeline."""
    start_time = datetime.now()
    
    print("\n" + "="*70)
    print("  DUMA BOKO: GOVERNANCE PROMISE-DELIVERY DIVERGENCE ENGINE")
    print("  v3.0 - Strategic Reconstruction Mode")
    print("="*70)
    
    # Paths
    targets_path = Path(args.config)
    divergence_results_path = Path(args.output)
    report_dir = Path("outputs/reports")
    
    # 1. RECONSTRUCTION PHASE
    # This runs the target_search.py logic reframed for divergences
    results = run_divergence_engine(
        targets_path=targets_path,
        output_path=divergence_results_path,
        dry_run=args.dry_run
    )
    
    if args.dry_run:
        print("\n[DRY RUN] Pipeline stopped after theme analysis.")
        return

    cases = results.get('cases', [])
    if not cases:
        print("\nERROR: Reconstruction phase failed to produce cases.")
        return

    # 2. EXPORT PHASE
    print("\nGenerating Governance Divergence Report...")
    exporter = WordExporter(report_dir)
    report_filename = f"DUMA_BOKO_DIVERGENCE_REPORT_{datetime.now().strftime('%Y%m%d')}.docx"
    report_path = exporter.generate_report(cases, filename=report_filename)
    
    duration = datetime.now() - start_time
    
    print("\n" + "="*70)
    print("  RECONSTRUCTION COMPLETE")
    print("="*70)
    print(f"  Total Duration:   {duration.total_seconds():.1f} seconds")
    print(f"  Report Generated: {report_path}")
    print(f"  Themes Analyzed:  {len(cases)}")
    print("="*70 + "\n")

def main():
    parser = argparse.ArgumentParser(description='Governance Divergence Engine v3.0')
    parser.add_argument('--config', type=str, default='config/contradiction_targets.yaml',
                        help='Path to investigation themes config')
    parser.add_argument('--output', type=str, default='outputs/cases/divergence_cases.json',
                        help='Path to save divergence results')
    parser.add_argument('--dry-run', action='store_true',
                        help='Show target expansion without executing reconstruction')
    
    args = parser.parse_args()
    
    try:
        run_pipeline(args)
    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
    except Exception as e:
        logger.exception("Pipeline failed with error")
        print(f"\nFATAL ERROR: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
