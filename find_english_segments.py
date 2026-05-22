#!/usr/bin/env python3
"""
Find all English segments for contradiction analysis.
"""
import json
from pathlib import Path

def find_english_segments():
    """Find and analyze English-only segments."""
    print("="*70)
    print("FINDING ENGLISH SEGMENTS")
    print("="*70)
    
    segments_file = Path("extracted_segments.json")
    if not segments_file.exists():
        print("[ERROR] extracted_segments.json not found")
        return
    
    with open(segments_file, 'r', encoding='utf-8') as f:
        data = json.load(f)
    
    all_segments = data.get('all_segments', [])
    
    # Filter for English segments only
    english_segments = [s for s in all_segments if s.get('language') == 'en']
    
    print(f"\nTotal segments: {len(all_segments)}")
    print(f"English segments: {len(english_segments)}")
    print(f"Percentage: {len(english_segments)/len(all_segments)*100:.1f}%")
    
    # Group by video
    by_video = {}
    for seg in english_segments:
        vid = seg.get('video_id', 'unknown')
        if vid not in by_video:
            by_video[vid] = []
        by_video[vid].append(seg)
    
    print(f"\n{'='*70}")
    print("ENGLISH SEGMENTS BY VIDEO")
    print(f"{'='*70}")
    
    for video_id, segments in sorted(by_video.items(), key=lambda x: len(x[1]), reverse=True):
        print(f"\n{video_id}: {len(segments)} segments")
        # Show longest segment
        longest = max(segments, key=lambda x: x.get('word_count', 0))
        print(f"  Longest: {longest['text'][:120]}...")
    
    # Save English-only data
    output = {
        'total_english_segments': len(english_segments),
        'segments_by_video': {k: len(v) for k, v in by_video.items()},
        'english_segments': english_segments
    }
    
    output_file = Path("english_segments.json")
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*70}")
    print(f"Saved to: {output_file}")
    print(f"{'='*70}")
    
    return english_segments

if __name__ == "__main__":
    find_english_segments()
