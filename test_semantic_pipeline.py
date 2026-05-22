#!/usr/bin/env python3
"""
test_semantic_pipeline.py - Comprehensive test of the semantic pipeline.

Runs the semantic pipeline in test mode and validates all outputs exist
with expected structure and content.

Usage:
    python test_semantic_pipeline.py
    python test_semantic_pipeline.py --full
"""

import sys
import json
import argparse
from pathlib import Path


def verify_json_file(filepath: Path, min_items: int = 0) -> tuple:
    """
    Verify a JSON file exists and has expected structure.
    
    Returns:
        (success: bool, item_count: int, message: str)
    """
    if not filepath.exists():
        return False, 0, f"File does not exist: {filepath}"
    
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # Determine item count based on file structure
        item_count = 0
        if isinstance(data, dict):
            if 'segments' in data:
                item_count = len(data.get('segments', []))
            elif 'claims' in data:
                item_count = len(data.get('claims', []))
            elif 'pairs' in data:
                item_count = len(data.get('pairs', []))
            elif 'scored_pairs' in data:
                item_count = len(data.get('scored_pairs', []))
            elif 'cases' in data:
                item_count = len(data.get('cases', []))
            elif 'priority_cases' in data:
                item_count = len(data.get('priority_cases', []))
        elif isinstance(data, list):
            item_count = len(data)
        
        # Check minimum items
        if item_count < min_items:
            return False, item_count, f"Expected at least {min_items} items, found {item_count}"
        
        return True, item_count, f"OK ({item_count} items)"
    
    except json.JSONDecodeError as e:
        return False, 0, f"Invalid JSON: {e}"
    except Exception as e:
        return False, 0, f"Error reading file: {e}"


def verify_csv_file(filepath: Path, min_rows: int = 0) -> tuple:
    """
    Verify a CSV file exists and has expected structure.
    
    Returns:
        (success: bool, row_count: int, message: str)
    """
    if not filepath.exists():
        return False, 0, f"File does not exist: {filepath}"
    
    try:
        import csv
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.reader(f)
            rows = list(reader)
        
        # First row is header
        data_rows = len(rows) - 1 if rows else 0
        
        if data_rows < min_rows:
            return False, data_rows, f"Expected at least {min_rows} data rows, found {data_rows}"
        
        return True, data_rows, f"OK ({data_rows} data rows)"
    
    except Exception as e:
        return False, 0, f"Error reading file: {e}"


def test_semantic_pipeline(test_mode: bool = True, full_run: bool = False):
    """Test the semantic pipeline."""
    
    print("="*70)
    print("SEMANTIC PIPELINE TEST")
    print("="*70)
    print()
    
    # Define expected outputs
    expected_files = [
        ('JSON', 'outputs/claims/routed_segments.json', 1),
        ('JSON', 'outputs/claims/translated_segments.json', 1),
        ('JSON', 'outputs/claims/claims.json', 1),
        ('JSON', 'outputs/claims/topic_clustered_claims.json', 1),
        ('JSON', 'outputs/pairs/candidate_pairs.json', 0),  # May be empty
        ('JSON', 'outputs/pairs/scored_pairs.json', 0),     # May be empty
        ('JSON', 'outputs/cases/contradiction_cases.json', 0),  # May be empty
        ('CSV',  'outputs/cases/contradiction_cases.csv', 0),   # May be empty
        ('JSON', 'outputs/review/priority_cases.json', 0),   # May be empty
        ('CSV',  'outputs/review/priority_cases.csv', 0),    # May be empty
    ]
    
    all_passed = True
    results_summary = {
        'total_files': len(expected_files),
        'verified': 0,
        'missing': 0,
        'invalid': 0,
        'details': []
    }
    
    print(f"Testing {len(expected_files)} output files...")
    print("-"*70)
    
    for file_type, filepath_str, min_items in expected_files:
        filepath = Path(filepath_str)
        
        if file_type == 'JSON':
            success, item_count, message = verify_json_file(filepath, min_items)
        else:
            success, item_count, message = verify_csv_file(filepath, min_items)
        
        status = "✓" if success else "✗"
        
        print(f"{status} {filepath_str:<50} {message}")
        
        result = {
            'file': filepath_str,
            'type': file_type,
            'success': success,
            'item_count': item_count,
            'message': message
        }
        results_summary['details'].append(result)
        
        if success:
            results_summary['verified'] += 1
        elif not filepath.exists():
            results_summary['missing'] += 1
        else:
            results_summary['invalid'] += 1
        
        if not success:
            all_passed = False
    
    print()
    print("-"*70)
    print("SUMMARY")
    print("-"*70)
    print(f"Total files checked: {results_summary['total_files']}")
    print(f"Files verified: {results_summary['verified']}")
    print(f"Files missing: {results_summary['missing']}")
    print(f"Files invalid: {results_summary['invalid']}")
    print()
    
    if all_passed and results_summary['verified'] == results_summary['total_files']:
        print("✓ ALL TESTS PASSED")
        return 0
    else:
        print("✗ SOME TESTS FAILED")
        print("\nFailed files:")
        for detail in results_summary['details']:
            if not detail['success']:
                print(f"  - {detail['file']}: {detail['message']}")
        return 1


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Test the semantic evidence pipeline'
    )
    parser.add_argument(
        '--full',
        action='store_true',
        help='Run full pipeline (process all data, not just test data)'
    )
    parser.add_argument(
        '--run-first',
        action='store_true',
        help='Run the pipeline before testing'
    )
    
    args = parser.parse_args()
    
    if args.run_first:
        print("Running semantic pipeline first...")
        print()
        try:
            from run_semantic_pipeline import run_semantic_pipeline
            run_semantic_pipeline(
                test_mode=not args.full,
                skip_translation=False,
                min_contradiction_score=0.3,
                verbose=True
            )
            print()
        except Exception as e:
            print(f"ERROR running pipeline: {e}")
            import traceback
            traceback.print_exc()
            return 1
    
    # Test the outputs
    return test_semantic_pipeline(test_mode=not args.full, full_run=args.full)


if __name__ == '__main__':
    exit_code = main()
    sys.exit(exit_code)
