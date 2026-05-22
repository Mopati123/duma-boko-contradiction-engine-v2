#!/usr/bin/env python3
"""
priority_case_builder.py - Build priority cases from top contradictions.

Input: outputs/cases/contradiction_cases.json
Output: outputs/review/priority_cases.json
        outputs/review/priority_cases.csv

Selects top 5 strongest candidate cases and adds metadata for manual review.
"""

import os
import sys
import csv
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

sys.path.insert(0, str(Path(__file__).parent))
from evidence.evidence_schema import load_json, save_json


def extract_keywords_from_text(text: str) -> List[str]:
    """Extract key terms from text for search suggestions."""
    if not text:
        return []
    
    # Simple keyword extraction - take significant words
    stop_words = {'the', 'a', 'an', 'and', 'or', 'is', 'was', 'be', 'to', 'of', 'in', 'for', 'on', 'at', 'by', 'from', 'as', 'with', 'will', 'shall', 'not', 'no', 'yes'}
    
    text_lower = text.lower()
    # Split on spaces and punctuation
    import re
    words = re.findall(r'\b[a-z]+\b', text_lower)
    
    # Filter out stop words and take most significant
    significant = [w for w in words if w not in stop_words and len(w) > 3]
    
    # Return top 5 most relevant
    return list(set(significant))[:5]


def generate_search_phrase_suggestion(claim_a_text: str, claim_b_text: str) -> str:
    """Generate a search phrase suggestion to find better sources."""
    keywords_a = extract_keywords_from_text(claim_a_text)
    keywords_b = extract_keywords_from_text(claim_b_text)
    
    # Combine top keywords from both claims
    combined = keywords_a + keywords_b
    
    # Remove duplicates while preserving order
    seen = set()
    unique = []
    for kw in combined:
        if kw not in seen:
            unique.append(kw)
            seen.add(kw)
    
    # Return top 3-4 keywords as phrase
    search_phrase = " ".join(unique[:4])
    return search_phrase if search_phrase else "duma boko speech"


def determine_evidence_gaps(case: Dict[str, Any]) -> List[str]:
    """Determine what evidence is missing for the case."""
    gaps = []
    
    claim_a_video = case.get('claim_a_source_video', '').strip()
    claim_b_video = case.get('claim_b_source_video', '').strip()
    
    # Check if both claims from same video
    if claim_a_video and claim_b_video:
        if claim_a_video == claim_b_video:
            gaps.append("Both claims from same video - need independent source for contradiction validation")
    
    # Check score strength
    score = case.get('contradiction_score', 0)
    if score < 0.5:
        gaps.append("Low confidence score - higher quality sources needed for verification")
    elif score < 0.7:
        gaps.append("Medium confidence - additional corroborating evidence recommended")
    
    # Check time gap
    claim_a_start = case.get('claim_a_start', 0)
    claim_b_start = case.get('claim_b_start', 0)
    
    time_diff = abs(claim_b_start - claim_a_start)
    if time_diff > 3600:  # More than 1 hour apart in same video
        gaps.append("Large time gap within video - context may be missing")
    
    # Check if topics are well matched
    topic_a = case.get('claim_a_topic', '')
    topic_b = case.get('claim_b_topic', '')
    
    if topic_a != topic_b:
        gaps.append(f"Topics differ ({topic_a} vs {topic_b}) - may indicate weak link")
    
    return gaps if gaps else ["Additional context needed for final verification"]


def build_priority_cases(
    contradiction_cases_path: Path,
    output_json_path: Path,
    output_csv_path: Path,
    top_n: int = 5
) -> Dict[str, Any]:
    """
    Build priority cases from top contradictions.
    
    Args:
        contradiction_cases_path: Path to contradiction_cases.json
        output_json_path: Where to save priority_cases.json
        output_csv_path: Where to save priority_cases.csv
        top_n: Number of top cases to include
    
    Returns:
        Dictionary with results
    """
    # Load cases
    data = load_json(contradiction_cases_path)
    cases = data.get('cases', [])
    
    print(f"Loaded {len(cases)} contradiction cases")
    
    if not cases:
        print("No cases to process - creating empty output")
        empty_output = {
            'metadata': {
                'created_at': datetime.now().isoformat(),
                'pipeline_stage': 'priority_case_building',
                'version': '1.0',
                'total_cases': 0
            },
            'statistics': {
                'total_cases': 0,
                'priority_cases': 0
            },
            'priority_cases': []
        }
        
        os.makedirs(output_json_path.parent, exist_ok=True)
        save_json(empty_output, str(output_json_path))
        
        # Create empty CSV
        os.makedirs(output_csv_path.parent, exist_ok=True)
        with open(output_csv_path, 'w', newline='', encoding='utf-8') as f:
            writer = csv.writer(f)
            writer.writerow(['priority_rank', 'case_id', 'contradiction_score', 'evidence_strength',
                           'why_selected', 'evidence_missing', 'search_phrase', 'verification_status'])
        
        return empty_output
    
    # Sort cases by contradiction score (descending)
    sorted_cases = sorted(cases, key=lambda c: c.get('contradiction_score', 0), reverse=True)
    
    # Select top N
    priority_cases_list = sorted_cases[:top_n]
    
    print(f"Selected top {len(priority_cases_list)} cases")
    
    # Add priority metadata
    priority_cases = []
    
    for rank, case in enumerate(priority_cases_list, 1):
        score = case.get('contradiction_score', 0)
        strength = case.get('evidence_strength', 'unknown')
        case_id = case.get('case_id', f'CASE_{rank:04d}')
        
        # Generate why_selected
        why_selected = f"Strong contradiction match (score: {score:.3f}, strength: {strength})"
        
        # Generate evidence gaps
        evidence_gaps = determine_evidence_gaps(case)
        evidence_missing = "; ".join(evidence_gaps)
        
        # Generate search phrase
        claim_a_text = case.get('claim_a_translated_text', '')
        claim_b_text = case.get('claim_b_translated_text', '')
        search_phrase = generate_search_phrase_suggestion(claim_a_text, claim_b_text)
        
        priority_case = {
            'priority_rank': rank,
            'case_id': case_id,
            'contradiction_score': score,
            'evidence_strength': strength,
            'contradiction_type': case.get('contradiction_type', 'unknown'),
            'why_selected': why_selected,
            'what_evidence_missing': evidence_missing,
            'search_phrase_suggestion': search_phrase,
            'verification_status': 'unverified',
            'claim_a_type': case.get('claim_a_type', ''),
            'claim_a_topic': case.get('claim_a_topic', ''),
            'claim_a_original_text': case.get('claim_a_original_text', '')[:300],
            'claim_a_translated_text': case.get('claim_a_translated_text', '')[:300],
            'claim_a_source_video': case.get('claim_a_source_video', ''),
            'claim_b_type': case.get('claim_b_type', ''),
            'claim_b_topic': case.get('claim_b_topic', ''),
            'claim_b_original_text': case.get('claim_b_original_text', '')[:300],
            'claim_b_translated_text': case.get('claim_b_translated_text', '')[:300],
            'claim_b_source_video': case.get('claim_b_source_video', ''),
            'reasoning': case.get('reasoning', '')[:500],
            'full_case': case  # Include full case for reference
        }
        
        priority_cases.append(priority_case)
    
    # Build output
    output_json = {
        'metadata': {
            'created_at': datetime.now().isoformat(),
            'pipeline_stage': 'priority_case_building',
            'version': '1.0',
            'total_cases_available': len(cases),
            'top_n': top_n
        },
        'statistics': {
            'total_cases': len(cases),
            'priority_cases': len(priority_cases)
        },
        'priority_cases': priority_cases
    }
    
    # Save JSON
    os.makedirs(output_json_path.parent, exist_ok=True)
    save_json(output_json, str(output_json_path))
    print(f"✓ Saved {len(priority_cases)} priority cases to {output_json_path}")
    
    # Save CSV
    os.makedirs(output_csv_path.parent, exist_ok=True)
    with open(output_csv_path, 'w', newline='', encoding='utf-8') as f:
        fieldnames = [
            'priority_rank',
            'case_id',
            'contradiction_score',
            'evidence_strength',
            'contradiction_type',
            'why_selected',
            'what_evidence_missing',
            'search_phrase_suggestion',
            'verification_status',
            'claim_a_type',
            'claim_a_topic',
            'claim_b_type',
            'claim_b_topic'
        ]
        
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        for case in priority_cases:
            writer.writerow({
                'priority_rank': case['priority_rank'],
                'case_id': case['case_id'],
                'contradiction_score': case['contradiction_score'],
                'evidence_strength': case['evidence_strength'],
                'contradiction_type': case['contradiction_type'],
                'why_selected': case['why_selected'],
                'what_evidence_missing': case['what_evidence_missing'],
                'search_phrase_suggestion': case['search_phrase_suggestion'],
                'verification_status': case['verification_status'],
                'claim_a_type': case['claim_a_type'],
                'claim_a_topic': case['claim_a_topic'],
                'claim_b_type': case['claim_b_type'],
                'claim_b_topic': case['claim_b_topic']
            })
    
    print(f"✓ Saved {len(priority_cases)} priority cases to CSV: {output_csv_path}")
    
    # Return result
    result = {
        'metadata': output_json['metadata'],
        'statistics': output_json['statistics']
    }
    
    print(f"\n✓ Priority case building complete")
    print(f"  Total cases available: {len(cases)}")
    print(f"  Priority cases selected: {len(priority_cases)}")
    
    return result


def main():
    parser = argparse.ArgumentParser(
        description='Build priority cases from contradiction cases'
    )
    parser.add_argument(
        '--input',
        type=str,
        default='outputs/cases/contradiction_cases.json',
        help='Input contradiction cases file'
    )
    parser.add_argument(
        '--output-json',
        type=str,
        default='outputs/review/priority_cases.json',
        help='Output JSON file path'
    )
    parser.add_argument(
        '--output-csv',
        type=str,
        default='outputs/review/priority_cases.csv',
        help='Output CSV file path'
    )
    parser.add_argument(
        '--top-n',
        type=int,
        default=5,
        help='Number of top cases to select'
    )
    
    args = parser.parse_args()
    
    input_path = Path(args.input)
    output_json_path = Path(args.output_json)
    output_csv_path = Path(args.output_csv)
    
    if not input_path.exists():
        print(f"ERROR: Input file not found: {input_path}")
        sys.exit(1)
    
    result = build_priority_cases(
        input_path,
        output_json_path,
        output_csv_path,
        top_n=args.top_n
    )
    
    sys.exit(0)


if __name__ == '__main__':
    main()
