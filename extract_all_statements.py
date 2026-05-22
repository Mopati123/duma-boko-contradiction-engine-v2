#!/usr/bin/env python3
"""
Extract ALL statements from transcripts (Swahili-friendly).
Simply pulls sentences with reasonable length and completeness.
"""
import json
from pathlib import Path
from typing import List, Dict

def extract_all_substantive_statements():
    """Extract all substantive statements from transcripts."""
    print("="*70)
    print("EXTRACTING ALL SUBSTANTIVE STATEMENTS")
    print("="*70)
    
    transcript_dir = Path("downloads/TRANSCRIPTS")
    output_file = Path("all_statements_extracted.json")
    
    if not transcript_dir.exists():
        print(f"[ERROR] Transcript directory not found")
        return
    
    transcript_files = list(transcript_dir.glob("*.transcript.json"))
    print(f"Found {len(transcript_files)} transcript files\n")
    
    all_statements = []
    
    for i, transcript_file in enumerate(transcript_files, 1):
        print(f"[{i}/{len(transcript_files)}] Processing {transcript_file.name}...")
        
        try:
            with open(transcript_file, 'r', encoding='utf-8') as f:
                data = json.load(f)
        except Exception as e:
            print(f"  [ERROR] Failed to load: {e}")
            continue
        
        video_id = data.get('video_id', transcript_file.stem.replace('.transcript', ''))
        transcript = data.get('transcript', [])
        
        found = 0
        for segment in transcript:
            text = segment.get('text', '').strip()
            if not text:
                continue
            
            # Extract ALL segments with reasonable length (3+ words)
            words = len(text.split())
            if words >= 3:
                statement = {
                    'text': text,
                    'video_id': video_id,
                    'timestamp': f"{segment.get('start', 0):.1f}",
                    'duration': f"{segment.get('end', 0) - segment.get('start', 0):.1f}",
                    'word_count': words,
                    'language': data.get('language', 'unknown')
                }
                all_statements.append(statement)
                found += 1
        
        print(f"  [OK] Extracted {found} statements")
    
    # Sort by length (longer statements are often more substantive)
    all_statements.sort(key=lambda x: x['word_count'], reverse=True)
    
    # Save results
    output_data = {
        'extraction_method': 'all_substantive',
        'total_transcripts': len(transcript_files),
        'total_statements': len(all_statements),
        'top_100_statements': all_statements[:100],
        'all_statements': all_statements
    }
    
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(output_data, f, indent=2, ensure_ascii=False)
    
    print(f"\n{'='*70}")
    print("EXTRACTION COMPLETE")
    print(f"{'='*70}")
    print(f"Total statements extracted: {len(all_statements)}")
    print(f"Saved to: {output_file}")
    
    # Display sample of longest statements
    print(f"\n{'='*70}")
    print("TOP 20 LONGEST STATEMENTS (Sample)")
    print(f"{'='*70}")
    
    for i, stmt in enumerate(all_statements[:20], 1):
        print(f"\n{i}. [{stmt['video_id']} @ {stmt['timestamp']}s] ({stmt['word_count']} words)")
        print(f"   {stmt['text'][:150]}{'...' if len(stmt['text']) > 150 else ''}")
    
    print(f"\n{'='*70}")
    print("NEXT STEPS:")
    print("1. Review all_statements_extracted.json")
    print("2. Manually identify key Duma Boko statements in Swahili")
    print("3. Use those as targets for contradiction detection")
    print(f"{'='*70}")

if __name__ == "__main__":
    extract_all_substantive_statements()
