#!/usr/bin/env python3
"""
Extract segments from transcripts (corrected version).
Uses 'segments' key instead of 'transcript'.
"""
import json
from pathlib import Path
from typing import List, Dict

def extract_segments():
    """Extract all segments from transcripts."""
    print("="*70)
    print("EXTRACTING SEGMENTS FROM TRANSCRIPTS")
    print("="*70)
    
    transcript_dir = Path("downloads/TRANSCRIPTS")
    output_file = Path("extracted_segments.json")
    
    if not transcript_dir.exists():
        print(f"[ERROR] Transcript directory not found")
        return
    
    transcript_files = list(transcript_dir.glob("*.transcript.json"))
    print(f"Found {len(transcript_files)} transcript files\n")
    
    all_segments = []
    
    for i, transcript_file in enumerate(transcript_files, 1):
        print(f"[{i}/{len(transcript_files)}] Processing {transcript_file.name}...")
        
        try:
            with open(transcript_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"  [ERROR] Failed to load: {e}")
            continue
        
        video_id = data.get('video_id', transcript_file.stem.replace('.transcript', ''))
        
        # Use 'segments' key (not 'transcript')
        segments = data.get('segments', [])
        
        found = 0
        for segment in segments:
            text = segment.get('text', '').strip()
            if not text:
                continue
            
            # Extract all segments with reasonable length (3+ words)
            words = len(text.split())
            if words >= 3:
                seg_data = {
                    'text': text,
                    'video_id': video_id,
                    'timestamp_start': segment.get('start', 0),
                    'timestamp_end': segment.get('end', 0),
                    'word_count': words,
                    'language': data.get('language', 'unknown'),
                    'confidence': segment.get('confidence', 0)
                }
                all_segments.append(seg_data)
                found += 1
        
        print(f"  [OK] Extracted {found} segments")
    
    # Sort by length (longer segments are often more substantive)
    all_segments.sort(key=lambda x: x['word_count'], reverse=True)
    
    # Save results
    output_data = {
        'extraction_method': 'all_segments',
        'total_transcripts': len(transcript_files),
        'total_segments': len(all_segments),
        'top_100_segments': all_segments[:100],
        'all_segments': all_segments
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*70}")
    print("EXTRACTION COMPLETE")
    print(f"{'='*70}")
    print(f"Total segments extracted: {len(all_segments)}")
    print(f"Saved to: {output_file}")
    
    # Display sample of longest segments
    print(f"\n{'='*70}")
    print("TOP 20 LONGEST SEGMENTS (Sample)")
    print(f"{'='*70}")
    
    for i, seg in enumerate(all_segments[:20], 1):
        print(f"\n{i}. [{seg['video_id']} @ {seg['timestamp_start']:.1f}s] ({seg['word_count']} words)")
        print(f"   {seg['text'][:150]}{'...' if len(seg['text']) > 150 else ''}")
    
    print(f"\n{'='*70}")
    print("NEXT STEPS:")
    print("1. Review extracted_segments.json")
    print("2. Manually identify key Duma Boko statements")
    print("3. Use those as targets for contradiction detection")
    print(f"{'='*70}")

if __name__ == "__main__":
    extract_segments()
