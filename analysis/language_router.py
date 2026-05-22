#!/usr/bin/env python3
"""
language_router.py - Route transcript segments by language.

Input: Whisper transcript JSON files from downloads/TRANSCRIPTS/
Output: outputs/claims/routed_segments.json

For each segment:
- Detect language (from Whisper output or re-detect if missing)
- Preserve original text
- Mark for translation if not English
- Output normalized segment records
"""

import os
import sys
import json
import argparse
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))
from evidence.evidence_schema import SegmentRecord, save_json


def load_transcript(transcript_path: Path) -> Dict[str, Any]:
    """Load a Whisper transcript JSON file."""
    with open(transcript_path, 'r', encoding='utf-8') as f:
        return json.load(f)


def get_language(segment: Dict[str, Any], default_language: str = "unknown") -> str:
    """
    Extract language from segment or transcript metadata.
    Whisper provides language at transcript level; segments don't have individual language.
    """
    # Try to get language from segment (some Whisper versions include it)
    if 'language' in segment:
        return segment['language']
    
    # Return default - actual language is at transcript level
    return default_language


def route_segments(
    transcript_path: Path,
    video_id: str,
    default_language: str = "unknown"
) -> List[SegmentRecord]:
    """
    Route all segments from a transcript file.
    
    Args:
        transcript_path: Path to Whisper transcript JSON
        video_id: Video ID extracted from filename
        default_language: Language code from transcript metadata
    
    Returns:
        List of SegmentRecord objects
    """
    transcript = load_transcript(transcript_path)
    
    # Get language from transcript metadata
    if 'language' in transcript:
        default_language = transcript['language']
    
    segments = transcript.get('segments', [])
    routed = []
    
    for seg in segments:
        segment_id = f"{video_id}_{seg.get('id', len(routed))}"
        
        # Determine if translation is needed
        language = get_language(seg, default_language)
        requires_translation = language != "en"
        
        record = SegmentRecord(
            segment_id=segment_id,
            source_video_id=video_id,
            source_transcript_file=str(transcript_path.name),
            start=seg.get('start', 0.0),
            end=seg.get('end', 0.0),
            language=language,
            original_text=seg.get('text', '').strip(),
            requires_translation=requires_translation,
            metadata={
                'confidence': seg.get('confidence', 0.0),
                'transcript_language': default_language
            }
        )
        
        routed.append(record)
    
    return routed


def process_all_transcripts(
    transcripts_dir: Path,
    output_path: Path,
    test_mode: bool = False
) -> Dict[str, Any]:
    """
    Process all transcript files in directory.
    
    Args:
        transcripts_dir: Directory containing transcript JSON files
        output_path: Where to save routed_segments.json
        test_mode: If True, process only first transcript
    
    Returns:
        Dictionary with processing results and statistics
    """
    all_segments = []
    stats = {
        'total_transcripts': 0,
        'processed_transcripts': 0,
        'total_segments': 0,
        'english_segments': 0,
        'non_english_segments': 0,
        'languages_found': set()
    }
    
    # Find all transcript files
    transcript_files = list(transcripts_dir.glob("*.transcript.json"))
    stats['total_transcripts'] = len(transcript_files)
    
    if test_mode and transcript_files:
        transcript_files = [transcript_files[0]]
        print(f"[TEST MODE] Processing only: {transcript_files[0].name}")
    
    print(f"Processing {len(transcript_files)} transcript files...")
    
    for transcript_file in transcript_files:
        video_id = transcript_file.stem.replace('.transcript', '')
        
        try:
            segments = route_segments(transcript_file, video_id)
            all_segments.extend(segments)
            
            stats['processed_transcripts'] += 1
            stats['total_segments'] += len(segments)
            
            for seg in segments:
                stats['languages_found'].add(seg.language)
                if seg.requires_translation:
                    stats['non_english_segments'] += 1
                else:
                    stats['english_segments'] += 1
            
            print(f"  ✓ {transcript_file.name}: {len(segments)} segments ({sum(1 for s in segments if s.requires_translation)} need translation)")
            
        except Exception as e:
            print(f"  ✗ {transcript_file.name}: ERROR - {e}")
            continue
    
    # Convert set to list for JSON serialization
    stats['languages_found'] = list(stats['languages_found'])
    
    # Build output
    output = {
        'metadata': {
            'created_at': datetime.now().isoformat(),
            'pipeline_stage': 'language_routing',
            'version': '1.0',
            'test_mode': test_mode
        },
        'statistics': stats,
        'segments': [seg.to_dict() for seg in all_segments]
    }
    
    # Save output
    os.makedirs(output_path.parent, exist_ok=True)
    save_json(output, str(output_path))
    
    print(f"\n✓ Language routing complete")
    print(f"  Total segments: {stats['total_segments']}")
    print(f"  English: {stats['english_segments']}")
    print(f"  Non-English (need translation): {stats['non_english_segments']}")
    print(f"  Languages found: {', '.join(stats['languages_found'])}")
    print(f"  Output: {output_path}")
    
    return output


def main():
    parser = argparse.ArgumentParser(
        description='Route transcript segments by language'
    )
    parser.add_argument(
        '--transcripts-dir',
        type=str,
        default='downloads/TRANSCRIPTS',
        help='Directory containing transcript JSON files'
    )
    parser.add_argument(
        '--output',
        type=str,
        default='outputs/claims/routed_segments.json',
        help='Output file path'
    )
    parser.add_argument(
        '--test-one',
        action='store_true',
        help='Process only first transcript (test mode)'
    )
    
    args = parser.parse_args()
    
    transcripts_dir = Path(args.transcripts_dir)
    output_path = Path(args.output)
    
    if not transcripts_dir.exists():
        print(f"ERROR: Transcripts directory not found: {transcripts_dir}")
        sys.exit(1)
    
    result = process_all_transcripts(
        transcripts_dir,
        output_path,
        test_mode=args.test_one
    )
    
    # Return success if we processed at least one segment
    if result['statistics']['total_segments'] > 0:
        sys.exit(0)
    else:
        print("WARNING: No segments processed")
        sys.exit(1)


if __name__ == '__main__':
    main()
