#!/usr/bin/env python3
"""
Semantic pipeline orchestration for batch_processor.py

Adds language routing, translation, claim extraction, topic clustering, 
temporal pairing, contradiction detection, and case building to the batch processor.

Usage:
    python batch_processor.py --semantic --test-one
    python batch_processor.py --semantic --skip-translation
    python batch_processor.py --semantic --min-contradiction-score 0.6
"""

import sys
import os
import argparse
import subprocess
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))


def run_semantic_pipeline(test_mode=False, skip_translation=False, 
                        min_contradiction_score=0.3, verbose=True):
    """
    Run the complete semantic analysis pipeline.
    
    Pipeline stages:
    1. Language routing
    2. Translation
    3. Claim extraction
    4. Topic clustering
    5. Temporal pairing
    6. Contradiction detection
    7. Case building
    
    Args:
        test_mode: If True, process only 1-10 items per stage
        skip_translation: If True, skip translation stage
        min_contradiction_score: Minimum score threshold for output
        verbose: If True, print detailed progress
    
    Returns:
        Dictionary with results from each stage
    """
    
    results = {}
    
    print("\n" + "="*70)
    print("SEMANTIC EVIDENCE PIPELINE")
    print("="*70)
    print(f"Mode: {'TEST (limited data)' if test_mode else 'FULL DATASET'}")
    print(f"Min contradiction score: {min_contradiction_score}")
    print(f"Skip translation: {skip_translation}")
    print()
    
    # Stage 1: Language Routing
    print("[STAGE 1] Language Routing")
    print("-" * 70)
    try:
        from analysis.language_router import process_all_transcripts
        
        output_path = Path("outputs/claims/routed_segments.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        result = process_all_transcripts(
            Path("downloads/TRANSCRIPTS"),
            output_path,
            test_mode=test_mode
        )
        results['language_routing'] = result['statistics']
        print()
    except Exception as e:
        print(f"ERROR in language routing: {e}")
        import traceback
        traceback.print_exc()
        return results
    
    # Stage 2: Translation
    print("[STAGE 2] Translation")
    print("-" * 70)
    try:
        from analysis.translator import translate_segments
        
        output_path = Path("outputs/claims/translated_segments.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        result = translate_segments(
            Path("outputs/claims/routed_segments.json"),
            output_path,
            skip_translation=skip_translation,
            test_mode=test_mode
        )
        results['translation'] = result['statistics']
        print()
    except Exception as e:
        print(f"ERROR in translation: {e}")
        import traceback
        traceback.print_exc()
        return results
    
    # Stage 3: Claim Extraction
    print("[STAGE 3] Claim Extraction")
    print("-" * 70)
    try:
        from analysis.claim_extractor import extract_all_claims
        
        output_path = Path("outputs/claims/claims.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        result = extract_all_claims(
            Path("outputs/claims/translated_segments.json"),
            output_path,
            min_confidence=0.5,
            test_mode=test_mode
        )
        results['claim_extraction'] = result['statistics']
        print()
    except Exception as e:
        print(f"ERROR in claim extraction: {e}")
        import traceback
        traceback.print_exc()
        return results
    
    # Stage 4: Topic Clustering
    print("[STAGE 4] Topic Clustering")
    print("-" * 70)
    try:
        from analysis.topic_clusterer import cluster_claims
        
        output_path = Path("outputs/claims/topic_clustered_claims.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        result = cluster_claims(
            Path("outputs/claims/claims.json"),
            Path("config/topics.yaml"),
            output_path,
            test_mode=test_mode
        )
        results['topic_clustering'] = result['statistics']
        print()
    except Exception as e:
        print(f"ERROR in topic clustering: {e}")
        import traceback
        traceback.print_exc()
        return results
    
    # Stage 5: Temporal Pairing
    print("[STAGE 5] Temporal Pairing")
    print("-" * 70)
    try:
        from analysis.temporal_pairer import pair_claims
        
        output_path = Path("outputs/pairs/candidate_pairs.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        result = pair_claims(
            Path("outputs/claims/topic_clustered_claims.json"),
            output_path,
            min_confidence=0.5,
            test_mode=test_mode
        )
        results['temporal_pairing'] = result['statistics']
        print()
    except Exception as e:
        print(f"ERROR in temporal pairing: {e}")
        import traceback
        traceback.print_exc()
        return results
    
    # Stage 6: Contradiction Detection
    print("[STAGE 6] Contradiction Detection")
    print("-" * 70)
    try:
        from analysis.contradiction_engine import detect_contradictions
        
        output_path = Path("outputs/pairs/scored_pairs.json")
        output_path.parent.mkdir(parents=True, exist_ok=True)
        
        result = detect_contradictions(
            Path("outputs/pairs/candidate_pairs.json"),
            Path("config/contradiction_targets.yaml"),
            output_path,
            min_contradiction_score=min_contradiction_score,
            use_nli=False,  # Disable NLI for now (optional feature)
            test_mode=test_mode
        )
        results['contradiction_detection'] = result['statistics']
        print()
    except Exception as e:
        print(f"ERROR in contradiction detection: {e}")
        import traceback
        traceback.print_exc()
        return results
    
    # Stage 7: Case Building
    print("[STAGE 7] Case Building")
    print("-" * 70)
    try:
        from evidence.case_builder import build_cases
        
        output_json = Path("outputs/cases/contradiction_cases.json")
        output_csv = Path("outputs/cases/contradiction_cases.csv")
        output_json.parent.mkdir(parents=True, exist_ok=True)
        output_csv.parent.mkdir(parents=True, exist_ok=True)
        
        result = build_cases(
            Path("outputs/pairs/scored_pairs.json"),
            Path("outputs/claims/claims.json"),
            output_json,
            output_csv,
            test_mode=test_mode
        )
        results['case_building'] = result['statistics']
        print()
    except Exception as e:
        print(f"ERROR in case building: {e}")
        import traceback
        traceback.print_exc()
        return results
    
    # Stage 8: Priority Case Building
    print("[STAGE 8] Priority Case Building")
    print("-" * 70)
    try:
        from evidence.priority_case_builder import build_priority_cases
        
        output_json = Path("outputs/review/priority_cases.json")
        output_csv = Path("outputs/review/priority_cases.csv")
        
        result = build_priority_cases(
            Path("outputs/cases/contradiction_cases.json"),
            output_json,
            output_csv,
            top_n=5
        )
        results['priority_case_building'] = result['statistics']
        print()
    except Exception as e:
        print(f"ERROR in priority case building: {e}")
        import traceback
        traceback.print_exc()
        return results
    
    # Summary
    print("="*70)
    print("SEMANTIC PIPELINE COMPLETE")
    print("="*70)
    print("\nOutput files generated:")
    print("  ✓ outputs/claims/routed_segments.json")
    print("  ✓ outputs/claims/translated_segments.json")
    print("  ✓ outputs/claims/claims.json")
    print("  ✓ outputs/claims/topic_clustered_claims.json")
    print("  ✓ outputs/pairs/candidate_pairs.json")
    print("  ✓ outputs/pairs/scored_pairs.json")
    print("  ✓ outputs/cases/contradiction_cases.json")
    print("  ✓ outputs/cases/contradiction_cases.csv")
    print("  ✓ outputs/review/priority_cases.json")
    print("  ✓ outputs/review/priority_cases.csv")
    print()
    
    # Print detailed results
    if verbose:
        print("\nDetailed Results:")
        print("-" * 70)
        for stage_name, stats in results.items():
            print(f"\n{stage_name}:")
            if isinstance(stats, dict):
                for key, value in stats.items():
                    if not isinstance(value, dict):
                        print(f"  {key}: {value}")
    
    return results


def main():
    """Main entry point with semantic pipeline support."""
    parser = argparse.ArgumentParser(
        description='Batch Video Processor with Semantic Analysis Pipeline'
    )
    parser.add_argument(
        '--semantic',
        action='store_true',
        help='Enable semantic analysis pipeline (language routing, translation, claim extraction, etc.)'
    )
    parser.add_argument(
        '--test-one',
        action='store_true',
        help='Run in test mode (process limited data at each stage)'
    )
    parser.add_argument(
        '--skip-translation',
        action='store_true',
        help='Skip translation stage (use original text)'
    )
    parser.add_argument(
        '--min-contradiction-score',
        type=float,
        default=0.3,
        help='Minimum contradiction score for output (default: 0.3)'
    )
    
    args = parser.parse_args()
    
    if args.semantic:
        # Run semantic pipeline
        run_semantic_pipeline(
            test_mode=args.test_one,
            skip_translation=args.skip_translation,
            min_contradiction_score=args.min_contradiction_score,
            verbose=True
        )
    else:
        # Run traditional batch processor
        # Import and run the original batch processor from batch_processor.py
        print("Running traditional batch processor (non-semantic mode)")
        print("Use --semantic flag to enable semantic analysis pipeline")


if __name__ == '__main__':
    main()
